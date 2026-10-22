"""Explainable validation engine for student-level submissions.

Each check emits a finding with a stable rule code, severity, plain-language
message, evidence and the ruleset version, so institutions know exactly what to
fix and AICTE can audit why a record was flagged. Flags are review items, not
verdicts of fraud.

Severity semantics:
  ERROR   row is rejected and must be corrected and re-submitted
  WARNING row is accepted but opens a review item for AICTE / the institution
  INFO    row is accepted; the note is recorded for transparency
"""
import csv
import io
import math
from collections import defaultdict
from datetime import date, datetime

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config
from .apaar_registry import get_registry, is_valid_format, mask
from .models import Enrolment, Institution, Programme, Student

RULES: dict[str, tuple[str, str]] = {
    "SCH-001": ("ERROR", "Required field missing"),
    "SCH-002": ("ERROR", "Invalid field value"),
    "SCH-003": ("ERROR", "Invalid date"),
    "PRG-001": ("ERROR", "Programme not approved for this institution"),
    "APR-001": ("ERROR", "APAAR ID missing"),
    "APR-002": ("ERROR", "APAAR ID format invalid"),
    "APR-003": ("ERROR", "APAAR ID not found in registry"),
    "APR-004": ("WARNING", "Details do not match APAAR registry"),
    "APR-005": ("INFO", "Student opted out of APAAR, provisional ID issued"),
    "APR-006": ("ERROR", "APAAR ID is deactivated"),
    "APR-007": ("INFO", "APAAR not applicable (foreign national / OCI), provisional ID issued"),
    "DUP-001": ("ERROR", "Duplicate record within this upload"),
    "DUP-002": ("WARNING", "Already actively enrolled at another institution"),
    "DUP-003": ("WARNING", "Possible same person under a different APAAR ID"),
    "UPD-001": ("INFO", "Existing record will be updated"),
    "INT-001": ("ERROR", "Admission exceeds approved intake"),
    "INT-002": ("ERROR", "Supernumerary quota exceeded"),
    "CON-001": ("ERROR", "Foreign National without passport number"),
    "CON-002": ("ERROR", "OCI status without OCI card number"),
    "CON-003": ("WARNING", "Nationality conflicts with FN/OCI status"),
    "CON-004": ("WARNING", "NRI category without country of residence"),
    "CON-005": ("ERROR", "Lateral entry must be in year 2"),
    "CON-006": ("WARNING", "Admission date outside admission window"),
    "CON-007": ("WARNING", "Age implausible for programme level"),
    "CON-008": ("ERROR", "Quota inconsistent with nationality status"),
}

COLUMNS = [
    "apaar_id", "apaar_consent", "roll_no", "name", "dob", "gender", "category", "father_name",
    "programme_code", "year_of_study", "admission_type", "quota", "nationality", "fn_status",
    "oci_status", "oci_card_no", "passport_no", "nri_status", "nri_country", "pwd", "admission_date",
]
REQUIRED = ["roll_no", "name", "dob", "gender", "category", "father_name", "programme_code",
            "admission_type", "quota", "admission_date"]
ENUMS = {
    "gender": {"M", "F", "T"},
    "category": {"GEN", "OBC", "SC", "ST", "EWS"},
    "admission_type": {"REGULAR", "LATERAL"},
    "quota": {"STATE_CAP", "MANAGEMENT", "NRI", "TFW", "FN_OCI_PIO", "EWS_SN", "LATERAL"},
    "apaar_consent": {"GIVEN", "REFUSED"},
}
SUPERNUMERARY_BY_QUOTA = {"TFW": "TFW", "FN_OCI_PIO": "FN_OCI_PIO", "EWS_SN": "EWS", "LATERAL": "LATERAL"}

NAME_MATCH_MIN = 85
FUZZY_NAME_MIN = 88
FUZZY_FATHER_MIN = 85


def norm_name(name: str) -> str:
    """Lower-case, strip punctuation and drop initials so 'Ravi K. Rao' matches 'Ravi Rao'."""
    tokens = "".join(c if c.isalpha() else " " for c in (name or "").lower()).split()
    return " ".join(t for t in tokens if len(t) > 1)


def finding(code: str, message: str, **evidence) -> dict:
    severity, title = RULES[code]
    return {"code": code, "severity": severity, "title": title, "message": message,
            "evidence": evidence, "rule_version": config.RULESET_VERSION}


def _bool(v: str) -> bool:
    return str(v or "").strip().upper() in {"Y", "YES", "TRUE", "1"}


def _date(v: str) -> date | None:
    v = (v or "").strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            pass
    return None


def parse_csv(content: bytes) -> list[dict]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    return [{(k or "").strip().lower(): (v or "").strip() for k, v in row.items()} for row in reader]


def normalise(raw: dict) -> dict:
    r = {c: (raw.get(c) or "").strip() for c in COLUMNS}
    r["apaar_id"] = r["apaar_id"].replace(" ", "").replace("-", "")
    for c in ("gender", "category", "admission_type", "quota", "apaar_consent", "programme_code"):
        r[c] = r[c].upper()
    r["apaar_consent"] = r["apaar_consent"] or "GIVEN"
    r["nationality"] = r["nationality"] or "Indian"
    for c in ("fn_status", "oci_status", "nri_status", "pwd"):
        r[c] = _bool(r[c])
    r["year_of_study"] = int(r["year_of_study"]) if r["year_of_study"].isdigit() else 1
    return r


def age_on(dob: date, on: date) -> int:
    return on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))


class IntakeLedger:
    """Running seat count per programme: committed enrolments plus rows accepted so far."""

    def __init__(self, db: Session, programmes: dict[str, Programme]):
        self.intake = {p.id: p.approved_intake for p in programmes.values()}
        self.within: dict[int, int] = defaultdict(int)
        self.supernumerary: dict[tuple[int, str], int] = defaultdict(int)
        self.overflow: dict[tuple[int, str | None], int] = defaultdict(int)  # rejected attempts
        if not programmes:
            return
        rows = db.execute(
            select(Enrolment.programme_id, Enrolment.seat_type, Enrolment.supernumerary_type)
            .where(Enrolment.programme_id.in_(list(self.intake)), Enrolment.status == "ACTIVE",
                   Enrolment.admission_year == config.ADMISSION_YEAR)
        ).all()
        for pid, seat, sn in rows:
            if seat == "WITHIN_INTAKE":
                self.within[pid] += 1
            else:
                self.supernumerary[(pid, sn)] += 1

    def cap(self, pid: int, sn_type: str) -> int:
        return math.floor(self.intake[pid] * config.SUPERNUMERARY_CAPS[sn_type])


def validate_rows(db: Session, institution: Institution, raw_rows: list[dict]) -> list[dict]:
    registry = get_registry(db)
    programmes = {p.code: p for p in db.scalars(
        select(Programme).where(Programme.institution_id == institution.id,
                                Programme.academic_year == config.CURRENT_ACADEMIC_YEAR))}
    ledger = IntakeLedger(db, programmes)
    rows = [normalise(r) for r in raw_rows]

    apaars = {r["apaar_id"] for r in rows if r["apaar_id"]}
    existing: dict[str, list[Enrolment]] = defaultdict(list)
    if apaars:
        for e in db.scalars(select(Enrolment).join(Student)
                            .where(Student.apaar_id.in_(apaars), Enrolment.status == "ACTIVE")):
            existing[e.student.apaar_id].append(e)

    dobs = {d for d in (_date(r["dob"]) for r in rows) if d}
    by_dob: dict[date, list[Student]] = defaultdict(list)
    if dobs:
        for s in db.scalars(select(Student).where(Student.dob.in_(dobs))):
            by_dob[s.dob].append(s)

    win_start, win_end = (date.fromisoformat(d) for d in config.ADMISSION_WINDOW)
    seen_apaar: dict[str, int] = {}
    seen_roll: dict[str, int] = {}
    results = []

    for idx, r in enumerate(rows):
        row_no = idx + 2  # spreadsheet line number (line 1 is the header)
        f: list[dict] = []
        missing = [c for c in REQUIRED if not r[c]]
        if missing:
            f.append(finding("SCH-001", f"Missing: {', '.join(missing)}", fields=missing))
        for col, allowed in ENUMS.items():
            if r[col] and r[col] not in allowed:
                f.append(finding("SCH-002", f"{col} '{r[col]}' is not one of {sorted(allowed)}",
                                 field=col, value=r[col]))
        dob, adm = _date(r["dob"]), _date(r["admission_date"])
        for col, val in (("dob", dob), ("admission_date", adm)):
            if r[col] and val is None:
                f.append(finding("SCH-003", f"{col} '{r[col]}' is not a valid date (use YYYY-MM-DD)",
                                 field=col, value=r[col]))

        prog = programmes.get(r["programme_code"])
        if r["programme_code"] and prog is None:
            f.append(finding("PRG-001", f"Programme '{r['programme_code']}' is not approved for "
                             f"{config.CURRENT_ACADEMIC_YEAR}", approved=sorted(programmes)))

        # --- APAAR identity ---------------------------------------------------
        apaar = r["apaar_id"]
        is_update = False
        if not apaar:
            if r["fn_status"] or r["oci_status"]:
                f.append(finding("APR-007", "APAAR needs Aadhaar-based KYC, so it is optional for "
                                 "FN/OCI students. A provisional AICTE ID will be issued."))
            elif r["apaar_consent"] == "REFUSED":
                f.append(finding("APR-005", "No APAAR ID because the student declined consent. A "
                                 "provisional AICTE ID will be issued; this is not a defect."))
            else:
                f.append(finding("APR-001", "APAAR ID is blank and no consent refusal is recorded"))
        elif not is_valid_format(apaar):
            f.append(finding("APR-002", f"'{r['apaar_id']}' is not a 12-digit APAAR ID", value=apaar))
        else:
            reg = registry.lookup(apaar)
            if not reg.found:
                f.append(finding("APR-003", f"{mask(apaar)} does not exist in the APAAR registry",
                                 apaar=mask(apaar), source=reg.source))
            elif reg.status != "ACTIVE":
                f.append(finding("APR-006", f"{mask(apaar)} is {reg.status} in the registry"))
            else:
                sim = fuzz.token_sort_ratio(norm_name(r["name"]), norm_name(reg.name))
                dob_ok = dob == reg.dob
                if sim < NAME_MATCH_MIN or not dob_ok:
                    f.append(finding("APR-004", f"Submitted '{r['name']}' / {r['dob']} vs registry "
                                     f"'{reg.name}' / {reg.dob}", name_similarity=round(sim),
                                     submitted_name=r["name"], registry_name=reg.name,
                                     dob_match=dob_ok))
            if apaar in seen_apaar:
                f.append(finding("DUP-001", f"Same APAAR ID already appears on row {seen_apaar[apaar]}",
                                 first_row=seen_apaar[apaar]))
            else:
                seen_apaar[apaar] = row_no
            for e in existing.get(apaar, []):
                if e.institution_id == institution.id:
                    if prog and e.programme_id == prog.id:
                        is_update = True
                        f.append(finding("UPD-001", f"Existing enrolment {e.roll_no} will be updated"))
                else:
                    f.append(finding(
                        "DUP-002", f"Active enrolment at {e.institution.name} ({e.institution.aicte_pid}), "
                        f"{e.programme.name}, admitted {e.admission_date}",
                        other_institution=e.institution.name, other_pid=e.institution.aicte_pid,
                        other_institution_id=e.institution_id, other_programme=e.programme.name,
                        other_admission_date=str(e.admission_date)))
        if r["roll_no"]:
            if r["roll_no"] in seen_roll:
                f.append(finding("DUP-001", f"Roll number already used on row {seen_roll[r['roll_no']]}",
                                 first_row=seen_roll[r["roll_no"]]))
            else:
                seen_roll[r["roll_no"]] = row_no

        # --- probabilistic identity match (same person, different APAAR) ------
        if dob and r["name"]:
            for s in by_dob.get(dob, []):
                if s.apaar_id == apaar or s.gender != r["gender"]:
                    continue
                ns = fuzz.token_sort_ratio(norm_name(r["name"]), norm_name(s.name))
                fs = fuzz.token_sort_ratio(norm_name(r["father_name"]), norm_name(s.father_name))
                if ns >= FUZZY_NAME_MIN and fs >= FUZZY_FATHER_MIN:
                    other = db.scalars(select(Enrolment).where(Enrolment.student_id == s.id)).first()
                    f.append(finding(
                        "DUP-003", f"Matches {s.name} (APAAR {mask(s.apaar_id)}) at "
                        f"{other.institution.name if other else 'unknown'}: same DOB, name {ns:.0f}% "
                        f"and father's name {fs:.0f}% similar",
                        name_similarity=round(ns), father_similarity=round(fs),
                        matched_apaar=mask(s.apaar_id), matched_name=s.name,
                        other_institution=other.institution.name if other else None,
                        other_institution_id=other.institution_id if other else None))
                    break

        # --- consistency --------------------------------------------------------
        foreign = r["nationality"].lower() not in {"indian", "india"}
        if r["fn_status"] and not r["passport_no"]:
            f.append(finding("CON-001", "FN status is Yes but passport number is blank"))
        if r["oci_status"] and not r["oci_card_no"]:
            f.append(finding("CON-002", "OCI status is Yes but OCI card number is blank"))
        if (r["fn_status"] and not foreign) or (foreign and not (r["fn_status"] or r["oci_status"])):
            f.append(finding("CON-003", f"Nationality '{r['nationality']}' with FN={r['fn_status']}, "
                             f"OCI={r['oci_status']}"))
        if (r["nri_status"] or r["quota"] == "NRI") and not r["nri_country"]:
            f.append(finding("CON-004", "NRI category needs country of residence"))
        if r["quota"] == "FN_OCI_PIO" and not (r["fn_status"] or r["oci_status"] or foreign):
            f.append(finding("CON-008", "FN/OCI/PIO quota used for a resident Indian student"))
        lateral = r["admission_type"] == "LATERAL" or r["quota"] == "LATERAL"
        if lateral and r["year_of_study"] != 2:
            f.append(finding("CON-005", f"Lateral entry recorded in year {r['year_of_study']}"))
        if adm and not (win_start <= adm <= win_end):
            f.append(finding("CON-006", f"Admitted on {adm}, window is {win_start} to {win_end}",
                             admission_date=str(adm)))
        if dob and adm and prog:
            lo, hi = config.AGE_LIMITS.get(prog.level, (14, 60))
            age = age_on(dob, adm)
            if not lo <= age <= hi:
                f.append(finding("CON-007", f"Age {age} at admission; expected {lo}-{hi} for {prog.level}",
                                 age=age))

        # --- intake ledger (only rows that would otherwise be accepted) ---------
        sn_type = "LATERAL" if lateral else SUPERNUMERARY_BY_QUOTA.get(r["quota"])
        seat_type = "SUPERNUMERARY" if sn_type else "WITHIN_INTAKE"
        if prog and not is_update and not any(x["severity"] == "ERROR" for x in f):
            if sn_type:
                n, cap = ledger.supernumerary[(prog.id, sn_type)] + 1, ledger.cap(prog.id, sn_type)
                if n <= cap:
                    ledger.supernumerary[(prog.id, sn_type)] = n
                else:
                    ledger.overflow[(prog.id, sn_type)] += 1
                    n += ledger.overflow[(prog.id, sn_type)] - 1
                    f.append(finding("INT-002", f"{sn_type} seat #{n} exceeds the cap of {cap} "
                                     f"({config.SUPERNUMERARY_CAPS[sn_type]:.0%} of {prog.approved_intake})",
                                     quota=sn_type, seat_number=n, cap=cap))
            else:
                n = ledger.within[prog.id] + 1
                if n <= prog.approved_intake:
                    ledger.within[prog.id] = n
                else:
                    ledger.overflow[(prog.id, None)] += 1
                    n += ledger.overflow[(prog.id, None)] - 1
                    f.append(finding("INT-001", f"This would be admission #{n} in {prog.name}, "
                                     f"approved intake is {prog.approved_intake}",
                                     seat_number=n, approved_intake=prog.approved_intake))

        sev = {x["severity"] for x in f}
        status = "ERROR" if "ERROR" in sev else "WARNING" if "WARNING" in sev else "OK"
        results.append({
            "row_no": row_no, "status": status, "data": {**r, "seat_type": seat_type,
                                                         "supernumerary_type": sn_type},
            "programme_id": prog.id if prog else None, "is_update": is_update, "findings": f,
        })
    return results
