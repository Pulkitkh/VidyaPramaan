"""Business operations shared by the REST endpoints."""
from collections import defaultdict
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import audit, config
from .anomaly import score_institutions
from .apaar_registry import mask
from .auth import User
from .models import Enrolment, Finding, Institution, Programme, Student, UploadBatch
from .scan import run_scan
from .validation import _date, validate_rows

# Codes the national scan re-derives from committed data; batch copies would duplicate them.
SCAN_OWNED = {"DUP-002", "DUP-003", "CON-006", "INT-001", "INT-002", "APR-001", "APR-003"}


def create_batch(db: Session, inst: Institution, rows: list[dict], filename: str, user: User,
                 source: str = "CSV") -> UploadBatch:
    results = validate_rows(db, inst, rows)
    batch = UploadBatch(
        institution_id=inst.id, filename=filename, source=source, uploaded_by=user.username,
        total_rows=len(results), rows=rows, row_results=results,
        error_rows=sum(r["status"] == "ERROR" for r in results),
        warning_rows=sum(r["status"] == "WARNING" for r in results))
    db.add(batch)
    db.flush()
    audit.record(db, user.username, user.role, "UPLOAD_VALIDATED", "upload_batch", batch.id,
                 {"rows": batch.total_rows, "errors": batch.error_rows, "warnings": batch.warning_rows,
                  "file": filename, "ruleset": config.RULESET_VERSION})
    return batch


def commit_batch(db: Session, batch: UploadBatch, user: User) -> dict:
    inst = db.get(Institution, batch.institution_id)
    created = updated = 0
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
            updated += 1
            continue
        student = None
        if d["apaar_id"]:
            student = db.scalars(select(Student).where(Student.apaar_id == d["apaar_id"])).first()
        if student is None:
            student = Student(
                apaar_id=d["apaar_id"] or None, name=d["name"], dob=_parse(d["dob"]),
                gender=d["gender"], category=d["category"], father_name=d["father_name"],
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
            roll_no=d["roll_no"], admission_year=config.ADMISSION_YEAR, year_of_study=d["year_of_study"],
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
    audit.record(db, user.username, user.role, "UPLOAD_COMMITTED", "upload_batch", batch.id,
                 {"created": created, "updated": updated, "rejected": batch.error_rows})
    scan = run_scan(db)
    score_institutions(db)
    audit.record(db, "system", "SYSTEM", "NATIONAL_SCAN", "dataset", "national", scan)
    return {"created": created, "updated": updated, "rejected": batch.error_rows, "scan": scan}


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
            .where(Enrolment.institution_id == inst_id, Enrolment.status == "ACTIVE")
            .group_by(Enrolment.programme_id, Enrolment.seat_type, Enrolment.supernumerary_type)):
        counts[pid]["WITHIN" if seat == "WITHIN_INTAKE" else sn] += n
    out = []
    for p in progs:
        c = counts[p.id]
        sn = {k: {"used": c.get(k, 0),
                  "cap": int(p.approved_intake * v)} for k, v in config.SUPERNUMERARY_CAPS.items()}
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
                 "dual_enrolments": findings_by_rule.get("DUP-002", 0),
                 "identity_duplicates": findings_by_rule.get("DUP-003", 0),
                 "rejected_rows": sum(rejected_by_rule.values())},
        "supernumerary_by_type": sn_types, "findings_by_rule": findings_by_rule,
        "rejected_by_rule": rejected_by_rule, "states": states,
        "gender": gender, "category": category, "level": level,
        "top_risk": [{"id": i.id, "name": i.name, "state": i.state, "aicte_pid": i.aicte_pid,
                      "risk_score": i.risk_score, "reasons": i.risk_reasons} for i in top],
        "ruleset_version": config.RULESET_VERSION,
    }


def student_public(s: Student, reveal: bool = False) -> dict:
    return {"id": s.id, "apaar_id": s.apaar_id if reveal else mask(s.apaar_id),
            "provisional_id": s.provisional_id, "name": s.name, "dob": s.dob, "gender": s.gender,
            "category": s.category, "nationality": s.nationality, "fn_status": s.fn_status,
            "oci_status": s.oci_status, "nri_status": s.nri_status, "nri_country": s.nri_country,
            "pwd": s.pwd, "apaar_consent": s.apaar_consent}


def enrolment_dict(e: Enrolment) -> dict:
    return {"id": e.id, "roll_no": e.roll_no, "institution_id": e.institution_id,
            "institution": e.institution.name, "aicte_pid": e.institution.aicte_pid,
            "programme": e.programme.name, "programme_code": e.programme.code, "level": e.programme.level,
            "admission_year": e.admission_year, "year_of_study": e.year_of_study,
            "admission_type": e.admission_type, "quota": e.quota, "seat_type": e.seat_type,
            "supernumerary_type": e.supernumerary_type, "admission_date": e.admission_date,
            "status": e.status}
