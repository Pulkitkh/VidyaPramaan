"""Synthetic national dataset with planted anomalies, plus the demo upload file.

Everything here is fake: institutions, people, APAAR IDs. Anomalies are injected
on purpose so the validation engine, scan and risk model have something to find.
Run:  python -m app.seed
"""
import csv
import os
import random
from datetime import date, timedelta

from faker import Faker
from sqlalchemy import insert

from . import audit, config
from .anomaly import score_institutions
from .credentials import build_credential
from .db import Base, SessionLocal, engine
from .models import (ConsentRequest, Credential, Enrolment, Institution, MockApaarRecord, Programme,
                     Student, VerificationLog, now)
from .scan import run_scan

RNG = random.Random(2026)
FAKE = Faker("en_IN")
FAKE.seed_instance(2026)
SAMPLE_CSV = config.SAMPLE_CSV

# (state, AICTE region, relative weight, cities)
STATES = [
    ("Maharashtra", "Western", 16, ["Pune", "Mumbai", "Nagpur", "Nashik", "Aurangabad", "Kolhapur"]),
    ("Tamil Nadu", "Southern", 15, ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Salem"]),
    ("Andhra Pradesh", "South-Central", 10, ["Visakhapatnam", "Vijayawada", "Guntur", "Tirupati"]),
    ("Telangana", "South-Central", 9, ["Hyderabad", "Warangal", "Karimnagar"]),
    ("Karnataka", "South-Western", 9, ["Bengaluru", "Mysuru", "Mangaluru", "Belagavi"]),
    ("Uttar Pradesh", "Northern", 11, ["Lucknow", "Noida", "Kanpur", "Prayagraj", "Varanasi"]),
    ("Madhya Pradesh", "Central", 6, ["Bhopal", "Indore", "Jabalpur", "Gwalior"]),
    ("Gujarat", "Central", 6, ["Ahmedabad", "Vadodara", "Surat", "Rajkot"]),
    ("Rajasthan", "North-Western", 5, ["Jaipur", "Jodhpur", "Udaipur", "Kota"]),
    ("Kerala", "South-Western", 5, ["Thiruvananthapuram", "Kochi", "Kozhikode"]),
    ("West Bengal", "Eastern", 5, ["Kolkata", "Durgapur", "Siliguri"]),
    ("Haryana", "North-Western", 4, ["Gurugram", "Faridabad", "Kurukshetra"]),
    ("Punjab", "North-Western", 4, ["Mohali", "Ludhiana", "Jalandhar"]),
    ("Odisha", "Eastern", 4, ["Bhubaneswar", "Cuttack", "Rourkela"]),
    ("Chhattisgarh", "Central", 2, ["Raipur", "Bhilai"]),
    ("Uttarakhand", "Northern", 2, ["Dehradun", "Haridwar"]),
    ("Bihar", "Eastern", 2, ["Patna", "Gaya"]),
    ("Jharkhand", "Eastern", 2, ["Ranchi", "Jamshedpur"]),
    ("Delhi", "North-Western", 2, ["New Delhi"]),
    ("Himachal Pradesh", "North-Western", 1, ["Shimla", "Solan"]),
    ("Jammu and Kashmir", "North-Western", 1, ["Jammu", "Srinagar"]),
    ("Assam", "Eastern", 1, ["Guwahati"]),
    ("Goa", "Western", 1, ["Panaji"]),
    ("Puducherry", "Southern", 1, ["Puducherry"]),
    ("Tripura", "Eastern", 1, ["Agartala"]),
    ("Meghalaya", "Eastern", 1, ["Shillong"]),
]
NAMESAKES = ["Vivekananda", "Visvesvaraya", "Ramanujan", "Saraswati", "Shivaji", "Tagore", "Kalam",
             "Bhabha", "Raman", "Aryabhatta", "Chanakya", "Shankaracharya", "Basaveshwara", "Gurunanak",
             "Kabir", "Narayana", "Annamacharya", "Vidyasagar", "Sardar Patel", "Ambedkar"]
SUFFIX_BY_TYPE = {
    "Engineering": ["Institute of Technology", "College of Engineering", "Institute of Engineering & Technology"],
    "Management": ["Institute of Management", "School of Business", "Institute of Management Studies"],
    "Pharmacy": ["College of Pharmacy", "Institute of Pharmaceutical Sciences"],
    "Polytechnic": ["Polytechnic", "Government Polytechnic"],
}
PROGRAMMES = {
    "Engineering": [("BTCSE", "UG", "B.Tech Computer Science & Engg.", [60, 120, 180]),
                    ("BTECE", "UG", "B.Tech Electronics & Communication", [60, 120]),
                    ("BTME", "UG", "B.Tech Mechanical Engg.", [60, 120]),
                    ("BTCE", "UG", "B.Tech Civil Engg.", [60]),
                    ("BTAIDS", "UG", "B.Tech AI & Data Science", [60, 120]),
                    ("MTCSE", "PG", "M.Tech Computer Science", [18, 24]),
                    ("MBA", "PG", "MBA", [60, 120]),
                    ("MCA", "PG", "MCA", [60, 120])],
    "Management": [("MBA", "PG", "MBA", [60, 120, 180]), ("PGDM", "PG", "PGDM", [60, 120]),
                   ("BBA", "UG", "BBA", [60, 120])],
    "Pharmacy": [("BPHARM", "UG", "B.Pharm", [60, 100]), ("MPHARM", "PG", "M.Pharm", [15, 30]),
                 ("DPHARM", "DIPLOMA", "D.Pharm", [60])],
    "Polytechnic": [("DCSE", "DIPLOMA", "Diploma Computer Engg.", [60, 120]),
                    ("DME", "DIPLOMA", "Diploma Mechanical Engg.", [60]),
                    ("DCE", "DIPLOMA", "Diploma Civil Engg.", [60]),
                    ("DEE", "DIPLOMA", "Diploma Electrical Engg.", [60])],
}
AGE_BY_LEVEL = {"UG": (17, 19), "PG": (21, 26), "DIPLOMA": (15, 17)}
FN_COUNTRIES = ["Nepal", "Bangladesh", "Afghanistan", "Sri Lanka", "Nigeria", "Bhutan", "Kenya", "Tanzania"]
NRI_COUNTRIES = ["UAE", "Qatar", "Oman", "Kuwait", "Saudi Arabia", "USA", "UK", "Singapore"]
LATERAL_CODES = {"BTCSE", "BTECE", "BTME", "BTCE", "BTAIDS", "BPHARM"}

used_apaar: set[str] = set()


def new_apaar() -> str:
    while True:
        a = str(RNG.randint(10**11, 10**12 - 1))
        if a not in used_apaar:
            used_apaar.add(a)
            return a


def person(level: str) -> dict:
    g = RNG.choices(["M", "F", "T"], [62, 37.8, 0.2])[0]
    first = FAKE.first_name_female() if g == "F" else FAKE.first_name_male()
    last = FAKE.last_name()
    lo, hi = AGE_BY_LEVEL[level]
    dob = date(2026 - RNG.randint(lo, hi), 1, 1) + timedelta(days=RNG.randint(0, 364))
    return {"name": f"{first} {last}", "gender": g, "dob": dob,
            "father_name": f"{FAKE.first_name_male()} {last}",
            "category": RNG.choices(["GEN", "OBC", "SC", "ST", "EWS"], [35, 35, 15, 7, 8])[0]}


def variant(name: str) -> str:
    parts = name.split()
    choice = RNG.randint(0, 2)
    if choice == 0 and len(parts) >= 2:
        return f"{parts[0]} {RNG.choice('KRSMP')}. {' '.join(parts[1:])}"
    if choice == 1 and len(parts) >= 2:
        return " ".join(parts[1:] + parts[:1])
    return name.replace("ee", "i").replace("oo", "u").replace("w", "v") if any(
        x in name for x in ("ee", "oo", "w")) else name + "a"


def adm_date(late: bool = False) -> date:
    if late:
        return date(2026, 10, 1) + timedelta(days=RNG.randint(0, 19))
    return date(2026, 7, 1) + timedelta(days=RNG.randint(0, 85))


class Builder:
    def __init__(self):
        self.institutions, self.programmes, self.students, self.enrolments = [], [], [], []
        self.registry: dict[str, dict] = {}
        self.sid = self.eid = 0

    def student(self, p: dict, apaar: str | None, register: bool = True, **extra) -> int:
        self.sid += 1
        rec = {"id": self.sid, "apaar_id": apaar, "provisional_id": None, "nationality": "Indian",
               "fn_status": False, "oci_status": False, "oci_card_no": None, "passport_no": None,
               "nri_status": False, "nri_country": None, "pwd": RNG.random() < 0.01,
               "apaar_consent": "GIVEN", **{k: p[k] for k in ("name", "gender", "dob", "father_name",
                                                               "category")}, **extra}
        if apaar is None and (rec["apaar_consent"] == "REFUSED" or rec["fn_status"] or rec["oci_status"]):
            rec["provisional_id"] = f"PRV-{self.sid:08d}"
        self.students.append(rec)
        if apaar and register:
            self.registry[apaar] = {"apaar_id": apaar, "name": p["name"], "dob": p["dob"],
                                    "gender": p["gender"], "status": "ACTIVE"}
        return self.sid

    def enrol(self, sid: int, inst: dict, prog: dict, seq: int, quota: str, sn_type: str | None,
              late: bool = False, lateral: bool = False) -> int:
        self.eid += 1
        self.enrolments.append({
            "id": self.eid, "student_id": sid, "institution_id": inst["id"], "programme_id": prog["id"],
            "roll_no": f"{inst['aicte_pid'][-4:]}{prog['code']}{26}{seq:03d}",
            "admission_year": 2026, "year_of_study": 2 if lateral else 1,
            "admission_type": "LATERAL" if lateral else "REGULAR", "quota": quota,
            "seat_type": "SUPERNUMERARY" if sn_type else "WITHIN_INTAKE", "supernumerary_type": sn_type,
            "admission_date": adm_date(late), "status": "ACTIVE", "created_at": now()})
        return self.eid


def build(n_institutions: int) -> tuple[Builder, dict]:
    b = Builder()
    weights = [s[2] for s in STATES]
    names_used = set()

    def add_inst(name, state, region, city, itype, pid):
        inst = {"id": len(b.institutions) + 1, "aicte_pid": pid, "name": name, "state": state,
                "city": city, "region": region, "inst_type": itype, "risk_score": 0.0,
                "risk_reasons": [], "quality_score": 100.0}
        b.institutions.append(inst)
        return inst

    def add_prog(inst, code, level, pname, intake):
        p = {"id": len(b.programmes) + 1, "institution_id": inst["id"], "code": code, "level": level,
             "name": pname, "academic_year": config.CURRENT_ACADEMIC_YEAR, "approved_intake": intake}
        b.programmes.append(p)
        return p

    demo = add_inst("Demo Institute of Technology, Pune", "Maharashtra", "Western", "Pune",
                    "Engineering", "1-9000000001")
    add_prog(demo, "BTCSE", "UG", "B.Tech Computer Science & Engg.", 60)
    for _ in range(n_institutions - 1):
        state, region, _, cities = RNG.choices(STATES, weights)[0]
        city = RNG.choice(cities)
        itype = RNG.choices(list(SUFFIX_BY_TYPE), [55, 20, 12, 13])[0]
        while True:
            name = f"{RNG.choice(['', 'Shri ', 'Sri ', 'Sant ', 'Dr. '])}{RNG.choice(NAMESAKES)} " \
                   f"{RNG.choice(SUFFIX_BY_TYPE[itype])}, {city}"
            if name not in names_used:
                names_used.add(name)
                break
        add_inst(name, state, region, city, itype, f"1-{RNG.randint(10**9, 10**10 - 1)}")

    # Choose which institutions carry which planted anomaly (never the demo institution).
    pool = [i["id"] for i in b.institutions[1:]]
    RNG.shuffle(pool)
    plant = {"over_intake": set(pool[0:10]), "ghost": set(pool[10:18]), "fn_excess": set(pool[18:23]),
             "apaar_gap": set(pool[23:31]), "identity_dup": set(pool[31:37]), "late": set(pool[37:42])}
    plant["fn_excess"] |= {pool[0]}  # one institution with compounded issues

    for inst in b.institutions:
        if inst["id"] == demo["id"]:
            progs = [add_prog(inst, "BTECE", "UG", "B.Tech Electronics & Communication", 60),
                     add_prog(inst, "MBA", "PG", "MBA", 60)]
        else:
            options = PROGRAMMES[inst["inst_type"]]
            chosen = RNG.sample(options, RNG.randint(2, min(5, len(options))))
            progs = [add_prog(inst, c, lvl, n, RNG.choice(sizes)) for c, lvl, n, sizes in chosen]
        over_progs = set(RNG.sample([p["id"] for p in progs], 1)) if inst["id"] in plant["over_intake"] else set()
        fn_prog = RNG.choice(progs)["id"] if inst["id"] in plant["fn_excess"] else None
        gap_rate = RNG.uniform(0.12, 0.25) if inst["id"] in plant["apaar_gap"] else 0.003
        late_rate = RNG.uniform(0.2, 0.35) if inst["id"] in plant["late"] else 0.004
        for p in progs:
            intake, seq = p["approved_intake"], 0
            if p["id"] in over_progs:
                n_within = round(intake * RNG.uniform(1.1, 1.32))
            elif inst["id"] == demo["id"]:
                n_within = intake - RNG.randint(4, 10)
            else:
                n_within = round(intake * min(1.0, RNG.betavariate(5, 1.6)))
            plan = [("STATE_CAP" if RNG.random() < 0.72 else "NRI" if RNG.random() < 0.15 else "MANAGEMENT",
                     None, False) for _ in range(n_within)]
            plan += [("TFW", "TFW", False)] * RNG.randint(0, int(intake * 0.05))
            fn_n = round(intake * RNG.uniform(0.2, 0.3)) if p["id"] == fn_prog else \
                RNG.choices([0, 1, 2], [70, 20, 10])[0]
            plan += [("FN_OCI_PIO", "FN_OCI_PIO", False)] * fn_n
            if p["code"] in LATERAL_CODES:
                plan += [("LATERAL", "LATERAL", True)] * RNG.randint(0, int(intake * 0.08))
            for quota, sn, lateral in plan:
                seq += 1
                pp = person(p["level"])
                if lateral:
                    pp["dob"] -= timedelta(days=365)
                extra = {}
                apaar = new_apaar()
                register = True
                if quota == "FN_OCI_PIO":
                    oci = RNG.random() < 0.25
                    extra = {"nationality": RNG.choice(["USA", "UK", "Canada"]) if oci else RNG.choice(FN_COUNTRIES),
                             "fn_status": not oci, "oci_status": oci,
                             "oci_card_no": f"A{RNG.randint(10**6, 10**7 - 1)}" if oci else None,
                             "passport_no": f"{RNG.choice('PKNZ')}{RNG.randint(10**6, 10**7 - 1)}"}
                    apaar = None
                elif quota == "NRI":
                    extra = {"nri_status": True, "nri_country": RNG.choice(NRI_COUNTRIES)}
                if apaar and RNG.random() < 0.006:
                    apaar, extra["apaar_consent"] = None, "REFUSED"
                elif apaar and RNG.random() < gap_rate:
                    if RNG.random() < 0.5:
                        apaar = None
                    else:
                        register = False
                sid = b.student(pp, apaar, register, **extra)
                b.enrol(sid, inst, p, seq, quota, sn, late=RNG.random() < late_rate, lateral=lateral)

    # Ghost / dual enrolment: the same registered student also enrolled elsewhere.
    by_inst: dict[int, list[dict]] = {}
    for e in b.enrolments:
        by_inst.setdefault(e["institution_id"], []).append(e)
    students = {s["id"]: s for s in b.students}
    prog_by_id = {p["id"]: p for p in b.programmes}
    inst_by_id = {i["id"]: i for i in b.institutions}
    for inst_id in plant["ghost"]:
        inst = inst_by_id[inst_id]
        target_prog = prog_by_id[by_inst[inst_id][0]["programme_id"]]
        donors = [e for e in b.enrolments if e["institution_id"] not in plant["ghost"] | {inst_id, demo["id"]}
                  and students[e["student_id"]]["apaar_id"] and e["seat_type"] == "WITHIN_INTAKE"]
        for k, e in enumerate(RNG.sample(donors, RNG.randint(12, 30))):
            b.enrol(e["student_id"], inst, target_prog, 900 + k, "MANAGEMENT", None)

    # Identity duplication: a near-identical person under a second, registered APAAR ID.
    for inst_id in plant["identity_dup"]:
        students = {s["id"]: s for s in b.students}
        inst = inst_by_id[inst_id]
        target_prog = prog_by_id[by_inst[inst_id][0]["programme_id"]]
        donors = [e for e in b.enrolments if e["institution_id"] not in {inst_id, demo["id"]}
                  and e["seat_type"] == "WITHIN_INTAKE" and students[e["student_id"]]["apaar_id"]]
        for k, e in enumerate(RNG.sample(donors, RNG.randint(6, 14))):
            src = students[e["student_id"]]
            pp = {**src, "name": variant(src["name"])}
            sid = b.student(pp, new_apaar())
            b.enrol(sid, inst, target_prog, 950 + k, "MANAGEMENT", None)

    # A few deactivated registry entries for realism.
    for a in RNG.sample(list(b.registry), 15):
        b.registry[a]["status"] = "DEACTIVATED"
    return b, {"demo": demo, "plant": {k: sorted(v) for k, v in plant.items()}}


def build_demo_csv(b: Builder, demo: dict) -> list[dict]:
    """Upload file for the demo institution's B.Tech CSE (intake 60) with planted defects."""
    students = {s["id"]: s for s in b.students}
    inst_by_id = {i["id"]: i for i in b.institutions}
    prog_by_id = {p["id"]: p for p in b.programmes}
    others = [e for e in b.enrolments if e["institution_id"] != demo["id"]
              and e["seat_type"] == "WITHIN_INTAKE" and students[e["student_id"]]["apaar_id"]
              and students[e["student_id"]]["apaar_id"] in b.registry
              and b.registry[students[e["student_id"]]["apaar_id"]]["status"] == "ACTIVE"
              and prog_by_id[e["programme_id"]]["level"] == "UG"
              and inst_by_id[e["institution_id"]]["inst_type"] == "Engineering"]
    rows: list[dict] = []

    def row(p, apaar="", **kw):
        r = {"apaar_id": apaar, "apaar_consent": "GIVEN", "roll_no": "", "name": p["name"],
             "dob": p["dob"].isoformat(), "gender": p["gender"], "category": p["category"],
             "father_name": p["father_name"], "programme_code": "BTCSE", "year_of_study": 1,
             "admission_type": "REGULAR", "quota": "STATE_CAP", "nationality": "Indian", "fn_status": "N",
             "oci_status": "N", "oci_card_no": "", "passport_no": "", "nri_status": "N", "nri_country": "",
             "pwd": "N", "admission_date": adm_date().isoformat()}
        r.update(kw)
        return r

    def clean(**kw):
        p = person("UG")
        a = new_apaar()
        b.registry[a] = {"apaar_id": a, "name": p["name"], "dob": p["dob"], "gender": p["gender"],
                         "status": "ACTIVE"}
        return row(p, a, **kw)

    specials = []
    for e in RNG.sample(others, 2):  # DUP-002 dual enrolment
        s = students[e["student_id"]]
        specials.append(row(s, s["apaar_id"]))
    src = students[RNG.choice(others)["student_id"]]  # DUP-003 same person, new APAAR
    p = {**src, "name": variant(src["name"])}
    a = new_apaar()
    b.registry[a] = {"apaar_id": a, "name": p["name"], "dob": p["dob"], "gender": p["gender"], "status": "ACTIVE"}
    specials.append(row(p, a))
    p = person("UG") | {"name": "Rohit Deshpande", "gender": "M", "father_name": "Mahesh Deshpande"}
    a = new_apaar()  # APR-004 registry has a different person
    b.registry[a] = {"apaar_id": a, "name": "Rohan Deshmukh", "dob": p["dob"] - timedelta(days=40),
                     "gender": "M", "status": "ACTIVE"}
    specials.append(row(p, a))
    specials.append(row(person("UG"), "", apaar_consent="REFUSED"))  # APR-005 opt-out
    specials.append(clean(quota="NRI", nri_status="Y"))  # CON-004
    young = person("UG")
    young["dob"] = date(2012, 5, 9)
    specials.append(row(young, new_apaar_registered(b, young)))  # CON-007
    errors = [
        row(person("UG"), ""), row(person("UG"), ""),  # APR-001
        row(person("UG"), "12345ABC9012"),  # APR-002
        row(person("UG"), new_apaar()),  # APR-003 (never registered)
        "DUP-001",
        row(person("UG") | {"category": "GEN"}, "", quota="FN_OCI_PIO", fn_status="Y",
            nationality="Nepal"),  # CON-001
        row(person("UG") | {"category": "GEN"}, "", quota="FN_OCI_PIO", oci_status="Y",
            nationality="USA", passport_no="Z8834512"),  # CON-002
        clean(admission_type="LATERAL", quota="LATERAL"),  # CON-005
    ]
    tfw = [clean(quota="TFW") for _ in range(4)]  # 4th exceeds 5% of 60 = 3
    fn_ok = [row(person("UG") | {"category": "GEN"}, "", quota="FN_OCI_PIO", fn_status="Y",
                 nationality=n, passport_no=f"P{RNG.randint(10**6, 10**7 - 1)}") for n in ("Nepal", "Bangladesh")]
    base = [clean() for _ in range(56)]
    body = base[:53] + specials + errors + tfw + fn_ok
    head, tail = body[:3], body[3:]
    RNG.shuffle(tail)
    body = head + tail
    dup_src = body[2]
    body = [dict(dup_src) if x == "DUP-001" else x for x in body]
    body += base[53:]  # the last three valid rows push admissions past intake
    for i, r in enumerate(body, 1):
        r["roll_no"] = f"0001BTCSE26{i:03d}"
    return body


def new_apaar_registered(b: Builder, p: dict) -> str:
    a = new_apaar()
    b.registry[a] = {"apaar_id": a, "name": p["name"], "dob": p["dob"], "gender": p["gender"], "status": "ACTIVE"}
    return a


def main(n_institutions: int | None = None) -> dict:
    n_institutions = n_institutions or int(os.getenv("VP_SEED_INSTITUTIONS", "240"))
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    b, meta = build(n_institutions)
    csv_rows = build_demo_csv(b, meta["demo"])
    SAMPLE_CSV.parent.mkdir(parents=True, exist_ok=True)
    with SAMPLE_CSV.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(csv_rows[0]))
        w.writeheader()
        w.writerows(csv_rows)

    db = SessionLocal()
    for model, rows in ((Institution, b.institutions), (Programme, b.programmes), (Student, b.students),
                        (Enrolment, b.enrolments), (MockApaarRecord, list(b.registry.values()))):
        for i in range(0, len(rows), 5000):
            db.execute(insert(model), rows[i:i + 5000])
    db.commit()
    if engine.dialect.name == "postgresql":
        # Rows were inserted with explicit ids; move each id sequence past them.
        from sqlalchemy import text
        for table in ("institution", "programme", "student", "enrolment"):
            db.execute(text(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                            f"(SELECT COALESCE(MAX(id), 1) FROM {table}))"))
        db.commit()
    audit.record(db, "system", "SYSTEM", "SEED_SYNTHETIC_DATA", "dataset", "national",
                 {"institutions": len(b.institutions), "students": len(b.students),
                  "enrolments": len(b.enrolments), "note": "synthetic demo data"})
    scan = run_scan(db)
    audit.record(db, "system", "SYSTEM", "NATIONAL_SCAN", "dataset", "national", scan)
    score_institutions(db)
    audit.record(db, "system", "SYSTEM", "RISK_SCORING", "dataset", "national", {"model": "IsolationForest+rules"})

    # Student persona with an issued credential and consent history.
    demo_ece = next(p for p in b.programmes if p["institution_id"] == meta["demo"]["id"] and p["code"] == "BTECE")
    by_sid = {x["id"]: x for x in b.students}
    persona_enrol = next(e for e in b.enrolments if e["programme_id"] == demo_ece["id"]
                         and by_sid[e["student_id"]]["apaar_id"] in b.registry
                         and b.registry[by_sid[e["student_id"]]["apaar_id"]]["status"] == "ACTIVE")
    s = db.get(Student, persona_enrol["student_id"])
    s.name, s.gender, s.father_name, s.dob = "Ananya Kulkarni", "F", "Suresh Kulkarni", date(2008, 3, 14)
    reg = db.get(MockApaarRecord, s.apaar_id)
    reg.name, reg.gender, reg.dob = s.name, s.gender, s.dob
    enrol = db.get(Enrolment, persona_enrol["id"])
    cred_id, vc, token = build_credential(s, enrol)
    db.add(Credential(id=cred_id, student_id=s.id, enrolment_id=enrol.id, vc=vc, token=token))
    audit.record(db, "inst.admin", "INSTITUTION_ADMIN", "CREDENTIAL_ISSUED", "credential", cred_id,
                 {"student": s.provisional_id or s.apaar_id[-4:]})
    c1 = ConsentRequest(student_id=s.id, verifier_org="Acme Technologies Pvt Ltd (demo employer)",
                        verifier_user="hr.verifier", purpose="Pre-joining education verification",
                        scope=["enrolment_status", "programme", "institution"], status="APPROVED",
                        otp="000000", expires_at=now() + timedelta(days=1), decided_at=now())
    db.add(c1)
    db.flush()
    db.add(VerificationLog(student_id=s.id, consent_id=c1.id, verifier_org=c1.verifier_org, basis="CONSENT",
                           purpose=c1.purpose, disclosed={"enrolment_status": "ACTIVE",
                                                          "programme": demo_ece["name"],
                                                          "institution": meta["demo"]["name"]}))
    db.add(ConsentRequest(student_id=s.id, verifier_org="National Scholarship Portal (demo)",
                          verifier_user="nsp.verifier", purpose="Scholarship eligibility check",
                          scope=["enrolment_status", "admission_year"], status="PENDING",
                          otp=f"{RNG.randint(0, 999999):06d}", expires_at=now() + timedelta(days=1)))
    db.commit()
    db.close()
    summary = {"institutions": len(b.institutions), "students": len(b.students),
               "enrolments": len(b.enrolments), "scan": scan, "planted": meta["plant"],
               "persona_student_id": persona_enrol["student_id"], "sample_csv": str(SAMPLE_CSV),
               "sample_rows": len(csv_rows)}
    (config.DATA_DIR / "seed_summary.json").write_text(__import__("json").dumps(summary, indent=1, default=str))
    return summary


if __name__ == "__main__":
    import json
    print(json.dumps(main(), indent=1, default=str))
