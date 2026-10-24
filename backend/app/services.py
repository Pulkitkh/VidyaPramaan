"""Business operations shared by the REST endpoints."""
import math
from collections import defaultdict
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import audit, config
from .anomaly import score_institutions
from .apaar_registry import mask
from .auth import User
from .models import Credential, Enrolment, Finding, Institution, Programme, Student, UploadBatch
from .scan import run_scan
from .validation import _date, map_columns, validate_rows

# Codes the national scan re-derives from committed data; batch copies would duplicate them.
SCAN_OWNED = {"DUP-002", "DUP-003", "DUP-004", "CON-006", "INT-001", "INT-002", "APR-001", "APR-003"}
EXIT_STATUSES = {"WITHDRAWN", "TRANSFERRED_OUT", "GRADUATED", "DROPPED"}


def create_batch(db: Session, inst: Institution, rows: list[dict], filename: str, user: User,
                 source: str = "CSV", idempotency_key: str | None = None) -> UploadBatch:
    rows, column_map, unknown = map_columns(rows)
    results = validate_rows(db, inst, rows)
    batch = UploadBatch(
        institution_id=inst.id, filename=filename, source=source, uploaded_by=user.username,
        total_rows=len(results), rows=rows, row_results=results, idempotency_key=idempotency_key,
        column_map={"renamed": column_map, "ignored": unknown},
        error_rows=sum(r["status"] == "ERROR" for r in results),
        warning_rows=sum(r["status"] == "WARNING" for r in results))
    db.add(batch)
    db.flush()
    audit.record(db, user.username, user.role, "UPLOAD_VALIDATED", "upload_batch", batch.id,
                 {"rows": batch.total_rows, "errors": batch.error_rows, "warnings": batch.warning_rows,
                  "file": filename, "ruleset": config.RULESET_VERSION})
    return batch


def commit_batch(db: Session, batch: UploadBatch, user: User, scan: bool = True) -> dict:
    inst = db.get(Institution, batch.institution_id)
    created = updated = unchanged = 0
    # Validate again against the data as it is now: another batch may have taken seats or added these
    # students since this one was checked. What is committed is always what the rules allow today.
    previous = {r["row_no"]: (r["status"], r["is_update"]) for r in batch.row_results}
    batch.row_results = validate_rows(db, inst, batch.rows)
    changed_rows = [r["row_no"] for r in batch.row_results if previous.get(r["row_no"]) != (r["status"], r["is_update"])]
    late_rejects = sum(1 for r in batch.row_results if r["status"] == "ERROR" and previous.get(r["row_no"], ("",))[0] != "ERROR")
    batch.error_rows = sum(r["status"] == "ERROR" for r in batch.row_results)
    batch.warning_rows = sum(r["status"] == "WARNING" for r in batch.row_results)
    for rr in batch.row_results:
        if rr["status"] == "ERROR":
            for f in rr["findings"]:
                if f["severity"] == "ERROR":
                    db.add(Finding(institution_id=inst.id, batch_id=batch.id, programme_id=rr["programme_id"],
                                   source="BATCH", rule_code=f["code"], severity="ERROR",
                                   message=f"Row {rr['row_no']} rejected: {f['message']}",
                                   evidence={**f["evidence"], "row_no": rr["row_no"]},
                                   rule_version=f["rule_version"], status="REJECTED"))
            continue
        d = rr["data"]
        if rr["is_update"]:
            enrol = db.get(Enrolment, rr["update_enrolment_id"])
            if enrol is not None:
                before = {c["field"]: c["old"] for c in rr.get("changes", [])}
                changed = _apply_update(enrol, d)
                if changed:
                    updated += 1
                    identity = sorted(set(changed) & {"name", "dob", "gender"})
                    superseded = 0
                    if identity:
                        # A credential carries the old name / DOB: replace it rather than leave it valid.
                        for c in db.scalars(select(Credential).where(Credential.enrolment_id == enrol.id,
                                                                     Credential.status == "ACTIVE")):
                            c.status, c.status_reason = "SUPERSEDED", f"{', '.join(identity)} corrected"
                            superseded += 1
                        db.add(Finding(institution_id=inst.id, batch_id=batch.id, enrolment_id=enrol.id,
                                       programme_id=enrol.programme_id, source="BATCH", rule_code="UPD-002",
                                       severity="WARNING",
                                       message=f"{enrol.student.name}: {', '.join(identity)} changed by re-upload",
                                       evidence={"changes": [c for c in rr.get("changes", [])
                                                             if c["field"] in identity],
                                                 "credentials_superseded": superseded},
                                       rule_version=config.RULESET_VERSION))
                    audit.record(db, user.username, user.role, "RECORD_UPDATED", "enrolment", enrol.id,
                                 {"fields": changed, "batch": batch.id,
                                  "before": {k: v for k, v in before.items() if k in changed}})
                else:
                    unchanged += 1
            continue
        student = None
        if d["apaar_id"]:
            student = db.scalars(select(Student).where(Student.apaar_id == d["apaar_id"])).first()
        if student is None:
            student = Student(
                apaar_id=d["apaar_id"] or None, name=d["name"], dob=_parse(d["dob"]),
                gender=d["gender"], category=d["category"], father_name=d["father_name"] or None,
                mother_name=d.get("mother_name") or None, guardian_name=d.get("guardian_name") or None,
                mobile=d.get("mobile") or None, email=d.get("email") or None,
                nationality=d["nationality"], fn_status=d["fn_status"], oci_status=d["oci_status"],
                oci_card_no=d["oci_card_no"] or None, passport_no=d["passport_no"] or None,
                nri_status=d["nri_status"], nri_country=d["nri_country"] or None, pwd=d["pwd"],
                apaar_consent=d["apaar_consent"])
            db.add(student)
            db.flush()
            if not student.apaar_id:
                student.provisional_id = f"PRV-{inst.aicte_pid[-4:]}-{student.id:06d}"
        enrol = Enrolment(
            student_id=student.id, institution_id=inst.id, programme_id=rr["programme_id"],
            roll_no=d["roll_no"], admission_year=d.get("admission_year", config.ADMISSION_YEAR),
            year_of_study=d["year_of_study"],
            admission_type=d["admission_type"], quota=d["quota"], seat_type=d["seat_type"],
            supernumerary_type=d["supernumerary_type"], admission_date=_parse(d["admission_date"]),
            batch_id=batch.id)
        db.add(enrol)
        db.flush()
        created += 1
        for f in rr["findings"]:
            if f["severity"] == "WARNING" and f["code"] not in SCAN_OWNED:
                db.add(Finding(institution_id=inst.id, batch_id=batch.id, enrolment_id=enrol.id,
                               programme_id=rr["programme_id"], source="BATCH", rule_code=f["code"],
                               severity="WARNING", message=f"{d['name']}: {f['message']}",
                               evidence=f["evidence"], rule_version=f["rule_version"]))
    batch.status = "COMMITTED"
    batch.committed_rows = created + updated
    db.flush()
    rejected = batch.error_rows
    audit.record(db, user.username, user.role, "UPLOAD_COMMITTED", "upload_batch", batch.id,
                 {"created": created, "updated": updated, "unchanged": unchanged, "rejected": rejected,
                  "changed_since_validation": len(changed_rows)})
    result = refresh_national(db) if scan else {"queued": True}
    return {"created": created, "updated": updated, "unchanged": unchanged, "rejected": rejected,
            "rejected_at_commit": late_rejects, "changed_since_validation": changed_rows, "scan": result}


def refresh_national(db: Session, actor: str = "system", role: str = "SYSTEM") -> dict:
    scan = run_scan(db)
    score_institutions(db)
    audit.record(db, actor, role, "NATIONAL_SCAN", "dataset", "national",
                 {k: scan[k] for k in ("findings", "new", "closed", "decisions_kept")})
    audit.checkpoint(db)
    return scan


def exit_enrolment(db: Session, enrol: Enrolment, status: str, on: date, reason: str, user: User) -> dict:
    """Record that a student left: withdrawal, transfer out, graduation or drop-out. Records are never deleted."""
    if status not in EXIT_STATUSES:
        raise ValueError(f"status must be one of {sorted(EXIT_STATUSES)}")
    if enrol.status != "ACTIVE":
        raise ValueError(f"Enrolment is already {enrol.status}")
    enrol.status, enrol.exit_date, enrol.exit_reason = status, on, reason
    revoked = 0
    for c in db.scalars(select(Credential).where(Credential.enrolment_id == enrol.id, Credential.status == "ACTIVE")):
        c.status, c.status_reason = "REVOKED", f"enrolment {status.lower().replace('_', ' ')} on {on}"
        revoked += 1
    audit.record(db, user.username, user.role, f"ENROLMENT_{status}", "enrolment", enrol.id,
                 {"date": on.isoformat(), "reason": reason, "credentials_revoked": revoked})
    db.flush()
    return {"enrolment_id": enrol.id, "status": status, "credentials_revoked": revoked}


UPDATABLE_STUDENT = ("name", "gender", "category", "father_name", "mother_name", "guardian_name", "nationality",
                     "fn_status", "oci_status", "oci_card_no", "passport_no", "nri_status", "nri_country", "pwd",
                     "mobile", "email")


def _apply_update(enrol: Enrolment, d: dict) -> list[str]:
    """Apply corrected student details. Quota and seat type are not changed by re-upload."""
    changed = []
    s = enrol.student
    for field in UPDATABLE_STUDENT:
        new = d.get(field) if isinstance(d.get(field), bool) else (d.get(field) or None)
        if field in ("name", "gender", "category", "father_name", "nationality"):
            new = new or getattr(s, field)
        if getattr(s, field) != new:
            setattr(s, field, new)
            changed.append(field)
    dob = _date(d["dob"])
    if dob and dob != s.dob:
        s.dob = dob
        changed.append("dob")
    adm = _date(d["admission_date"])
    if adm and adm != enrol.admission_date:
        enrol.admission_date = adm
        changed.append("admission_date")
    return changed


def _parse(v: str) -> date:
    d = _date(v)
    if d is None:
        raise ValueError(f"Bad date {v}")
    return d


def programme_ledger(db: Session, inst_id: int) -> list[dict]:
    progs = db.scalars(select(Programme).where(Programme.institution_id == inst_id)
                       .order_by(Programme.code)).all()
    counts = defaultdict(lambda: defaultdict(int))
    for pid, seat, sn, n in db.execute(
            select(Enrolment.programme_id, Enrolment.seat_type, Enrolment.supernumerary_type, func.count())
            .where(Enrolment.institution_id == inst_id, Enrolment.status == "ACTIVE",
                   Enrolment.admission_year == config.ADMISSION_YEAR)
            .group_by(Enrolment.programme_id, Enrolment.seat_type, Enrolment.supernumerary_type)):
        counts[pid]["WITHIN" if seat == "WITHIN_INTAKE" else sn] += n
    out = []
    for p in progs:
        c = counts[p.id]
        sn = {k: {"used": c.get(k, 0), "cap": math.floor(p.approved_intake * config.sn_cap_fraction(k, p.level))}
              for k in config.SUPERNUMERARY_TYPES}
        out.append({"programme_id": p.id, "code": p.code, "name": p.name, "level": p.level,
                    "approved_intake": p.approved_intake, "within_intake": c.get("WITHIN", 0),
                    "excess": max(0, c.get("WITHIN", 0) - p.approved_intake),
                    "utilisation": round(c.get("WITHIN", 0) / p.approved_intake, 3) if p.approved_intake else 0,
                    "supernumerary": sn})
    return out


def finding_dict(f: Finding, names: dict[int, str] | None = None) -> dict:
    names = names or {}
    return {"id": f.id, "institution_id": f.institution_id,
            "institution": names.get(f.institution_id) or (f.institution.name if f.institution else None),
            "related_institution_id": f.related_institution_id,
            "related_institution": names.get(f.related_institution_id),
            "enrolment_id": f.enrolment_id, "batch_id": f.batch_id, "source": f.source,
            "rule_code": f.rule_code, "severity": f.severity, "message": f.message, "evidence": f.evidence,
            "rule_version": f.rule_version, "status": f.status, "resolution_note": f.resolution_note,
            "created_at": f.created_at}


def national_dashboard(db: Session) -> dict:
    inst_count = db.scalar(select(func.count(Institution.id)))
    prog_count, intake = db.execute(select(func.count(Programme.id), func.sum(Programme.approved_intake))).one()
    seat = dict(db.execute(select(Enrolment.seat_type, func.count()).where(Enrolment.status == "ACTIVE")
                           .group_by(Enrolment.seat_type)).all())
    sn_types = dict(db.execute(select(Enrolment.supernumerary_type, func.count())
                               .where(Enrolment.status == "ACTIVE", Enrolment.seat_type == "SUPERNUMERARY")
                               .group_by(Enrolment.supernumerary_type)).all())
    total = sum(seat.values())
    with_apaar = db.scalar(select(func.count()).select_from(Enrolment).join(Student)
                           .where(Enrolment.status == "ACTIVE", Student.apaar_id.is_not(None)))
    opt_out = db.scalar(select(func.count()).select_from(Enrolment).join(Student)
                        .where(Enrolment.status == "ACTIVE", Student.apaar_consent == "REFUSED"))
    provisional_fn = db.scalar(select(func.count()).select_from(Enrolment).join(Student)
                               .where(Enrolment.status == "ACTIVE", Student.apaar_id.is_(None),
                                      (Student.fn_status | Student.oci_status)))
    findings_by_rule = dict(db.execute(select(Finding.rule_code, func.count()).where(Finding.status == "OPEN")
                                       .group_by(Finding.rule_code)).all())
    cases = open_cases(db)
    exited = db.scalar(select(func.count()).select_from(Enrolment).where(Enrolment.status != "ACTIVE"))
    rejected_by_rule = dict(db.execute(select(Finding.rule_code, func.count())
                                       .where(Finding.status == "REJECTED").group_by(Finding.rule_code)).all())

    # Per-state aggregates.
    st = defaultdict(lambda: {"institutions": 0, "intake": 0, "enrolled": 0, "high_risk": 0, "risk_sum": 0.0,
                              "excess": 0})
    insts = db.scalars(select(Institution)).all()
    for i in insts:
        s = st[i.state]
        s["institutions"] += 1
        s["risk_sum"] += i.risk_score
        s["high_risk"] += i.risk_score >= config.RISK_ALERT_THRESHOLD
    state_of = {i.id: i.state for i in insts}
    for inst_id, n in db.execute(select(Programme.institution_id, func.sum(Programme.approved_intake))
                                 .group_by(Programme.institution_id)):
        st[state_of[inst_id]]["intake"] += n
    within_by_prog = dict(db.execute(select(Enrolment.programme_id, func.count())
                                     .where(Enrolment.status == "ACTIVE", Enrolment.seat_type == "WITHIN_INTAKE")
                                     .group_by(Enrolment.programme_id)).all())
    excess_total = 0
    over_programmes = 0
    for p in db.scalars(select(Programme)):
        n = within_by_prog.get(p.id, 0)
        st[state_of[p.institution_id]]["enrolled"] += n
        if n > p.approved_intake:
            over_programmes += 1
            excess_total += n - p.approved_intake
            st[state_of[p.institution_id]]["excess"] += n - p.approved_intake
    states = []
    for name, s in sorted(st.items(), key=lambda kv: -kv[1]["intake"]):
        states.append({"state": name, "institutions": s["institutions"], "intake": s["intake"],
                       "enrolled": s["enrolled"], "utilisation": round(s["enrolled"] / s["intake"], 3) if s["intake"] else 0,
                       "high_risk": s["high_risk"], "excess": s["excess"],
                       "avg_risk": round(s["risk_sum"] / s["institutions"], 1)})

    gender = dict(db.execute(select(Student.gender, func.count()).join(Enrolment)
                             .where(Enrolment.status == "ACTIVE").group_by(Student.gender)).all())
    category = dict(db.execute(select(Student.category, func.count()).join(Enrolment)
                               .where(Enrolment.status == "ACTIVE").group_by(Student.category)).all())
    level = dict(db.execute(select(Programme.level, func.count()).join(Enrolment, Enrolment.programme_id == Programme.id)
                            .where(Enrolment.status == "ACTIVE").group_by(Programme.level)).all())
    top = sorted(insts, key=lambda i: -i.risk_score)[:10]
    return {
        "kpis": {"institutions": inst_count, "programmes": prog_count, "approved_intake": intake or 0,
                 "enrolled_within_intake": seat.get("WITHIN_INTAKE", 0),
                 "supernumerary": seat.get("SUPERNUMERARY", 0), "total_enrolments": total,
                 "apaar_coverage": round(with_apaar / total, 4) if total else 0, "apaar_opt_out": opt_out,
                 "provisional_fn_oci": provisional_fn,
                 "open_findings": sum(findings_by_rule.values()),
                 "high_risk_institutions": sum(i.risk_score >= config.RISK_ALERT_THRESHOLD for i in insts),
                 "programmes_over_intake": over_programmes, "excess_admissions": excess_total,
                 # Cases, not finding rows: one dual enrolment is one student, even though both
                 # institutions get a review item.
                 "dual_enrolments": cases.get("DUP-002", 0),
                 "identity_duplicates": cases.get("DUP-003", 0),
                 "shared_contact_clusters": cases.get("DUP-004", 0),
                 "exited_enrolments": exited,
                 "rejected_rows": sum(rejected_by_rule.values())},
        "cases_by_rule": cases,
        "supernumerary_by_type": sn_types, "findings_by_rule": findings_by_rule,
        "rejected_by_rule": rejected_by_rule, "states": states,
        "gender": gender, "category": category, "level": level,
        "top_risk": [{"id": i.id, "name": i.name, "state": i.state, "aicte_pid": i.aicte_pid,
                      "risk_score": i.risk_score, "reasons": i.risk_reasons} for i in top],
        "ruleset_version": config.RULESET_VERSION,
    }


def open_cases(db: Session) -> dict[str, int]:
    """Distinct open cases per rule (a dual enrolment flagged at two institutions is one case)."""
    cases = defaultdict(set)
    for code, ev, fid in db.execute(select(Finding.rule_code, Finding.evidence, Finding.id)
                                    .where(Finding.status == "OPEN")):
        cases[code].add((ev or {}).get("case") or f"F{fid}")
    return {k: len(v) for k, v in cases.items()}


def student_public(s: Student, reveal: bool = False) -> dict:
    return {"id": s.id, "apaar_id": s.apaar_id if reveal else mask(s.apaar_id),
            "provisional_id": s.provisional_id, "name": s.name, "dob": s.dob, "gender": s.gender,
            "category": s.category, "nationality": s.nationality, "fn_status": s.fn_status,
            "oci_status": s.oci_status, "nri_status": s.nri_status, "nri_country": s.nri_country,
            "pwd": s.pwd, "apaar_consent": s.apaar_consent, "father_name": s.father_name,
            "mother_name": s.mother_name, "guardian_name": s.guardian_name,
            "mobile": s.mobile if reveal else _mask_mobile(s.mobile),
            "email": s.email if reveal else _mask_email(s.email)}


def _mask_mobile(v: str | None) -> str | None:
    return f"{v[:2]}XXXXXX{v[-2:]}" if v else None


def _mask_email(v: str | None) -> str | None:
    if not v or "@" not in v:
        return None
    user, _, dom = v.partition("@")
    return f"{user[:1]}***@{dom}"


def enrolment_dict(e: Enrolment) -> dict:
    return {"id": e.id, "roll_no": e.roll_no, "institution_id": e.institution_id,
            "institution": e.institution.name, "aicte_pid": e.institution.aicte_pid,
            "programme": e.programme.name, "programme_code": e.programme.code, "level": e.programme.level,
            "admission_year": e.admission_year, "year_of_study": e.year_of_study,
            "admission_type": e.admission_type, "quota": e.quota, "seat_type": e.seat_type,
            "supernumerary_type": e.supernumerary_type, "admission_date": e.admission_date,
            "status": e.status, "exit_date": e.exit_date, "exit_reason": e.exit_reason,
            "university": e.institution.university}
