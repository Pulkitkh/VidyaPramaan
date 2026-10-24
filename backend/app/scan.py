"""Repository-wide scan over committed records.

Upload validation only sees one batch. This scan looks across all institutions
(intake overruns, dual enrolment, identity duplicates, shared-contact clusters,
registry gaps) and refreshes the SCAN findings that feed AICTE's review queue
and risk scores.

Every finding carries a fingerprint (rule + the records involved). The scan
reconciles against the findings already stored: an open item that is still true
keeps its id, one that is no longer true is closed, and an item an officer has
already resolved, dismissed or escalated is never re-opened for the same facts.
"""
import hashlib
import math
from collections import defaultdict

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from . import config
from .apaar_registry import is_valid_format, mask
from .matching import Person, match_key, quick_reject, same_person
from .models import Enrolment, Finding, Institution, MockApaarRecord, Programme, Student
from .validation import RULES, swapped

CLUSTER_MIN_STUDENTS = 4      # a parent's phone shared by siblings is normal; four or more is not
CLUSTER_MIN_SINGLE_SITE = 6   # at one institution, allow more before flagging (hostel warden, agent desk)


def _add(out: list, code: str, inst_id: int, message: str, fingerprint: str, *, programme_id=None,
         enrolment_id=None, related=None, **evidence):
    out.append(dict(institution_id=inst_id, programme_id=programme_id, enrolment_id=enrolment_id,
                    related_institution_id=related, source="SCAN", rule_code=code,
                    severity=RULES[code][0], message=message, evidence=evidence,
                    rule_version=config.RULESET_VERSION, status="OPEN", fingerprint=fingerprint))


def contact_key(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def mask_contact(value: str) -> str:
    if "@" in value:
        user, _, dom = value.partition("@")
        return f"{user[:1]}***@{dom}"
    return f"{value[:2]}XXXXXX{value[-2:]}"


def run_scan(db: Session) -> dict:
    out: list[dict] = []
    inst_names = dict(db.execute(select(Institution.id, Institution.name)).all())

    # Intake and supernumerary overruns per programme (current admission year).
    counts = db.execute(
        select(Enrolment.programme_id, Enrolment.seat_type, Enrolment.supernumerary_type, func.count())
        .where(Enrolment.status == "ACTIVE", Enrolment.admission_year == config.ADMISSION_YEAR)
        .group_by(Enrolment.programme_id, Enrolment.seat_type, Enrolment.supernumerary_type)).all()
    progs = {p.id: p for p in db.scalars(select(Programme))}
    for pid, seat, sn, n in counts:
        p = progs[pid]
        if seat == "WITHIN_INTAKE" and n > p.approved_intake:
            _add(out, "INT-001", p.institution_id,
                 f"{p.name}: {n} admitted within intake against approved {p.approved_intake} "
                 f"(+{n - p.approved_intake})", f"INT-001:{pid}:{n}", programme_id=pid,
                 enrolled=n, approved_intake=p.approved_intake, excess=n - p.approved_intake, case=f"P{pid}")
        elif seat == "SUPERNUMERARY" and sn in config.SUPERNUMERARY:
            frac = config.sn_cap_fraction(sn, p.level)
            cap = math.floor(p.approved_intake * frac)
            if n > cap:
                _add(out, "INT-002", p.institution_id,
                     f"{p.name}: {n} {sn} supernumerary seats against cap {cap} ({frac:.0%} for {p.level})",
                     f"INT-002:{pid}:{sn}:{n}", programme_id=pid, quota=sn, enrolled=n, cap=cap,
                     case=f"P{pid}:{sn}")

    # Same APAAR actively enrolled at more than one institution.
    multi = db.execute(
        select(Student.apaar_id).join(Enrolment).where(Enrolment.status == "ACTIVE",
                                                       Student.apaar_id.is_not(None))
        .group_by(Student.apaar_id).having(func.count(func.distinct(Enrolment.institution_id)) > 1)
    ).scalars().all()
    if multi:
        rows = db.execute(
            select(Student.apaar_id, Student.id.label("sid"), Enrolment.id, Enrolment.institution_id,
                   Enrolment.admission_date, Student.name).join(Enrolment)
            .where(Student.apaar_id.in_(multi), Enrolment.status == "ACTIVE")).all()
        groups = defaultdict(list)
        for r in rows:
            groups[r.apaar_id].append(r)
        for apaar, enrols in groups.items():
            for e in enrols:
                o = next(x for x in enrols if x.institution_id != e.institution_id)
                _add(out, "DUP-002", e.institution_id,
                     f"{e.name} ({mask(apaar)}) is also active at {inst_names[o.institution_id]}",
                     f"DUP-002:{e.id}", enrolment_id=e.id, related=o.institution_id, apaar=mask(apaar),
                     other_institution=inst_names[o.institution_id], institutions=len(enrols), case=f"S{e.sid}")

    # Probable same person under different APAAR IDs: blocked on date of birth (and day/month swaps) and
    # gender, then compared with the Indian-name matcher, which keeps twins and rhyming siblings apart.
    active_enrol: dict[int, tuple[int, int]] = {}
    for e_id, s_id, inst_id in db.execute(select(Enrolment.id, Enrolment.student_id, Enrolment.institution_id)
                                          .where(Enrolment.status == "ACTIVE").order_by(Enrolment.id)):
        active_enrol.setdefault(s_id, (e_id, inst_id))
    blocks: dict[tuple, list] = defaultdict(list)
    for s_id, name, father, mother, guardian, dob, gender, apaar in db.execute(
            select(Student.id, Student.name, Student.father_name, Student.mother_name, Student.guardian_name,
                   Student.dob, Student.gender, Student.apaar_id)):
        if s_id in active_enrol:
            words = frozenset(match_key(name).split())
            blocks[(dob, gender)].append((s_id, Person(name, dob, gender, father, mother, guardian), apaar, words))

    def compare(a, b):
        if a[2] and a[2] == b[2]:
            return  # same APAAR: that is DUP-002, not an identity duplicate
        # Cheap filters first: names sharing no word (after spelling normalisation) are skipped. This can miss
        # a pair where every word differs by a typing slip; such pairs are rare and still reach upload checks.
        if not (a[3] & b[3]) or quick_reject(a[1].name, b[1].name):
            return
        m = same_person(a[1], b[1])
        if not m.match:
            return
        (ea, ia), (eb, ib) = active_enrol[a[0]], active_enrol[b[0]]
        case = f"P{min(a[0], b[0])}-{max(a[0], b[0])}"
        for e, inst, other, other_e in ((ea, ia, ib, eb), (eb, ib, ia, ea)):
            where = "the same institution" if inst == other else inst_names[other]
            _add(out, "DUP-003", inst,
                 f"Probable same person as a student at {where} under a different APAAR ID "
                 f"({'; '.join(m.reasons[:2])})", f"DUP-003:{e}:{other_e}", enrolment_id=e, related=other,
                 score=m.score, name_score=m.name_score, parent_score=m.parent_score, reasons=m.reasons,
                 apaar_a=mask(a[2]), apaar_b=mask(b[2]), counterpart_enrolment=other_e, case=case)

    for (dob, gender), block in blocks.items():
        for i in range(len(block)):
            for j in range(i + 1, len(block)):
                compare(block[i], block[j])
        sw = swapped(dob)
        if sw and sw > dob:
            for a in block:
                for b in blocks.get((sw, gender), []):
                    compare(a, b)

    # Shared contact details: many students using one mobile number or e-mail, across institutions,
    # is a classic sign of agent-filled or ghost admissions. Siblings sharing a parent's phone are not flagged.
    by_contact: dict[tuple[str, str], list] = defaultdict(list)
    for s_id, name, mobile, email, apaar in db.execute(
            select(Student.id, Student.name, Student.mobile, Student.email, Student.apaar_id)):
        if s_id not in active_enrol:
            continue
        for kind, v in (("mobile", mobile), ("email", email)):
            if v:
                by_contact[(kind, v)].append((s_id, name, apaar))
    for (kind, value), members in by_contact.items():
        insts = {active_enrol[m[0]][1] for m in members}
        if len(members) < CLUSTER_MIN_STUDENTS or (len(insts) < 2 and len(members) < CLUSTER_MIN_SINGLE_SITE):
            continue
        key = contact_key(value)
        roster = [{"student_id": m[0], "name": m[1], "apaar": mask(m[2]),
                   "institution": inst_names[active_enrol[m[0]][1]]} for m in members[:40]]
        for s_id, _, _ in members:
            e_id, inst_id = active_enrol[s_id]
            _add(out, "DUP-004", inst_id,
                 f"The same {kind} ({mask_contact(value)}) is used by {len(members)} students at "
                 f"{len(insts)} institution{'s' * (len(insts) > 1)}", f"DUP-004:{e_id}:{key}",
                 enrolment_id=e_id, contact_type=kind, contact=mask_contact(value), students=len(members),
                 institutions=len(insts), members=roster, case=f"C{key}")

    # Registry gaps on committed records.
    registered = set(db.execute(select(MockApaarRecord.apaar_id)).scalars())
    for e_id, inst_id, apaar, consent, name, fn, oci in db.execute(
            select(Enrolment.id, Enrolment.institution_id, Student.apaar_id, Student.apaar_consent,
                   Student.name, Student.fn_status, Student.oci_status)
            .join(Student).where(Enrolment.status == "ACTIVE")):
        if not apaar and consent != "REFUSED" and not (fn or oci):
            _add(out, "APR-001", inst_id, f"{name}: APAAR ID missing without recorded refusal", f"APR-001:{e_id}",
                 enrolment_id=e_id, case=f"E{e_id}")
        elif apaar and (not is_valid_format(apaar) or apaar not in registered):
            _add(out, "APR-003", inst_id, f"{name}: {mask(apaar)} not found in APAAR registry", f"APR-003:{e_id}",
                 enrolment_id=e_id, apaar=mask(apaar), case=f"E{e_id}")

    # Admissions outside the window.
    start, end = config.ADMISSION_WINDOW
    for e_id, inst_id, adm in db.execute(
            select(Enrolment.id, Enrolment.institution_id, Enrolment.admission_date)
            .where(Enrolment.status == "ACTIVE", Enrolment.admission_year == config.ADMISSION_YEAR)):
        if not (start <= adm.isoformat() <= end):
            _add(out, "CON-006", inst_id, f"Admitted on {adm}, outside window {start} to {end}",
                 f"CON-006:{e_id}:{adm.isoformat()}", enrolment_id=e_id, admission_date=adm.isoformat(),
                 case=f"E{e_id}")

    return _reconcile(db, out)


def _reconcile(db: Session, out: list[dict]) -> dict:
    existing = {f.fingerprint: f for f in db.scalars(select(Finding).where(Finding.source == "SCAN"))}
    produced, new_rows, kept_decisions, refreshed = set(), [], 0, 0
    for d in out:
        fp = d["fingerprint"]
        if fp in produced:
            continue
        produced.add(fp)
        f = existing.get(fp)
        if f is None:
            new_rows.append(d)
        elif f.status == "OPEN":
            if f.message != d["message"] or f.evidence != d["evidence"]:
                f.message, f.evidence, f.rule_version = d["message"], d["evidence"], d["rule_version"]
                refreshed += 1
        else:
            kept_decisions += 1
    stale = [f.id for fp, f in existing.items() if fp not in produced and f.status == "OPEN"]
    if stale:
        db.execute(delete(Finding).where(Finding.id.in_(stale)))
    if new_rows:
        db.execute(Finding.__table__.insert(), new_rows)
    db.flush()
    by_code = defaultdict(int)
    cases = defaultdict(set)
    for d in out:
        by_code[d["rule_code"]] += 1
        cases[d["rule_code"]].add(d["evidence"].get("case"))
    return {"findings": len(produced), "new": len(new_rows), "closed": len(stale), "refreshed": refreshed,
            "decisions_kept": kept_decisions, "by_rule": dict(by_code),
            "cases_by_rule": {k: len(v) for k, v in cases.items()}}
