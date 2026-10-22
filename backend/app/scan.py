"""Repository-wide scan over committed records.

Upload validation only sees one batch. This scan looks across all institutions
(intake overruns, dual enrolment, identity duplicates, registry gaps) and
refreshes the SCAN findings that feed AICTE's review queue and risk scores.
"""
import math
from collections import defaultdict

from rapidfuzz import fuzz
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from . import config
from .apaar_registry import is_valid_format, mask
from .models import Enrolment, Finding, Institution, MockApaarRecord, Programme, Student
from .validation import FUZZY_FATHER_MIN, FUZZY_NAME_MIN, RULES, norm_name


def _add(out: list, code: str, inst_id: int, message: str, *, programme_id=None, enrolment_id=None,
         related=None, **evidence):
    out.append(dict(institution_id=inst_id, programme_id=programme_id, enrolment_id=enrolment_id,
                    related_institution_id=related, source="SCAN", rule_code=code,
                    severity=RULES[code][0], message=message, evidence=evidence,
                    rule_version=config.RULESET_VERSION, status="OPEN"))


def run_scan(db: Session) -> dict:
    db.execute(delete(Finding).where(Finding.source == "SCAN", Finding.status == "OPEN"))
    out: list[dict] = []
    inst_names = dict(db.execute(select(Institution.id, Institution.name)).all())

    # Intake and supernumerary overruns per programme.
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
                 f"(+{n - p.approved_intake})", programme_id=pid,
                 enrolled=n, approved_intake=p.approved_intake, excess=n - p.approved_intake)
        elif seat == "SUPERNUMERARY" and sn in config.SUPERNUMERARY_CAPS:
            cap = math.floor(p.approved_intake * config.SUPERNUMERARY_CAPS[sn])
            if n > cap:
                _add(out, "INT-002", p.institution_id,
                     f"{p.name}: {n} {sn} supernumerary seats against cap {cap}",
                     programme_id=pid, quota=sn, enrolled=n, cap=cap)

    # Same APAAR actively enrolled at more than one institution.
    multi = db.execute(
        select(Student.apaar_id).join(Enrolment).where(Enrolment.status == "ACTIVE",
                                                       Student.apaar_id.is_not(None))
        .group_by(Student.apaar_id).having(func.count(func.distinct(Enrolment.institution_id)) > 1)
    ).scalars().all()
    if multi:
        rows = db.execute(
            select(Student.apaar_id, Enrolment.id, Enrolment.institution_id, Enrolment.admission_date,
                   Student.name).join(Enrolment)
            .where(Student.apaar_id.in_(multi), Enrolment.status == "ACTIVE")).all()
        groups = defaultdict(list)
        for r in rows:
            groups[r.apaar_id].append(r)
        for apaar, enrols in groups.items():
            for e in enrols:
                others = [o for o in enrols if o.institution_id != e.institution_id]
                o = others[0]
                _add(out, "DUP-002", e.institution_id,
                     f"{e.name} ({mask(apaar)}) is also active at {inst_names[o.institution_id]}",
                     enrolment_id=e.id, related=o.institution_id, apaar=mask(apaar),
                     other_institution=inst_names[o.institution_id], institutions=len(enrols))

    # Probable same person under different APAAR IDs (blocked on DOB + gender).
    blocks = defaultdict(list)
    for s_id, name, father, dob, gender, apaar in db.execute(
            select(Student.id, Student.name, Student.father_name, Student.dob, Student.gender,
                   Student.apaar_id)):
        blocks[(dob, gender)].append((s_id, norm_name(name), norm_name(father), apaar))
    enrol_of = dict(db.execute(select(Enrolment.student_id, Enrolment.id)).all())
    inst_of = dict(db.execute(select(Enrolment.id, Enrolment.institution_id)).all())
    for block in blocks.values():
        for i in range(len(block)):
            for j in range(i + 1, len(block)):
                a, b = block[i], block[j]
                if a[3] == b[3]:
                    continue
                ns = fuzz.token_sort_ratio(a[1], b[1])
                if ns < FUZZY_NAME_MIN:
                    continue
                fs = fuzz.token_sort_ratio(a[2], b[2])
                if fs < FUZZY_FATHER_MIN:
                    continue
                ea, eb = enrol_of.get(a[0]), enrol_of.get(b[0])
                if not ea or not eb:
                    continue
                ia, ib = inst_of[ea], inst_of[eb]
                for e, inst, other in ((ea, ia, ib), (eb, ib, ia)):
                    _add(out, "DUP-003", inst,
                         f"Probable same person as a student at {inst_names[other]} "
                         f"(name {ns:.0f}%, father {fs:.0f}%, same DOB) under a different APAAR ID",
                         enrolment_id=e, related=other, name_similarity=round(ns),
                         father_similarity=round(fs), apaar_a=mask(a[3]), apaar_b=mask(b[3]))

    # Registry gaps on committed records.
    registered = set(db.execute(select(MockApaarRecord.apaar_id)).scalars())
    for e_id, inst_id, apaar, consent, name, fn, oci in db.execute(
            select(Enrolment.id, Enrolment.institution_id, Student.apaar_id, Student.apaar_consent,
                   Student.name, Student.fn_status, Student.oci_status)
            .join(Student).where(Enrolment.status == "ACTIVE")):
        if not apaar and consent != "REFUSED" and not (fn or oci):
            _add(out, "APR-001", inst_id, f"{name}: APAAR ID missing without recorded refusal",
                 enrolment_id=e_id)
        elif apaar and (not is_valid_format(apaar) or apaar not in registered):
            _add(out, "APR-003", inst_id, f"{name}: {mask(apaar)} not found in APAAR registry",
                 enrolment_id=e_id, apaar=mask(apaar))

    # Admissions outside the window.
    start, end = config.ADMISSION_WINDOW
    for e_id, inst_id, adm in db.execute(
            select(Enrolment.id, Enrolment.institution_id, Enrolment.admission_date)
            .where(Enrolment.status == "ACTIVE", Enrolment.admission_year == config.ADMISSION_YEAR)):
        if not (start <= adm.isoformat() <= end):
            _add(out, "CON-006", inst_id, f"Admitted on {adm}, outside window {start} to {end}",
                 enrolment_id=e_id, admission_date=adm.isoformat())

    if out:
        db.execute(Finding.__table__.insert(), out)
    db.flush()
    by_code = defaultdict(int)
    for f in out:
        by_code[f["rule_code"]] += 1
    return {"findings": len(out), "by_rule": dict(by_code)}
