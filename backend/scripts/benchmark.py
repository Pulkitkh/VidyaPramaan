"""Measure detection quality and speed on the synthetic dataset.

Ground truth comes from the seed: planted institutions are listed in
data/seed_summary.json, planted dual enrolments use roll-number sequence 900-949
and planted identity duplicates use 950-999.
Run from backend/:  python -m scripts.benchmark  (after python -m app.seed)
"""
import json
import time

from sqlalchemy import select

from app import config
from app.anomaly import score_institutions
from app.db import SessionLocal
from app.models import Enrolment, Finding, Institution, Student
from app.scan import run_scan
from app.validation import parse_csv, validate_rows


def main() -> dict:
    db = SessionLocal()
    summary = json.loads((config.DATA_DIR / "seed_summary.json").read_text())
    planted_insts = {i for ids in summary["planted"].values() for i in ids}

    t = time.perf_counter()
    scan = run_scan(db)
    scan_s = time.perf_counter() - t
    t = time.perf_counter()
    score_institutions(db)
    score_s = time.perf_counter() - t

    flagged = {(f.enrolment_id, f.rule_code) for f in db.scalars(select(Finding).where(Finding.status == "OPEN"))}
    enrols = db.scalars(select(Enrolment)).all()
    ghost = [e for e in enrols if 900 <= int(e.roll_no[-3:]) < 950]
    ident = [e for e in enrols if 950 <= int(e.roll_no[-3:]) < 1000]
    ghost_hit = sum((e.id, "DUP-002") in flagged for e in ghost)
    ident_hit = sum((e.id, "DUP-003") in flagged for e in ident)

    ranked = db.scalars(select(Institution).order_by(Institution.risk_score.desc())).all()
    k = len(planted_insts)
    top_k = {i.id for i in ranked[:k]}
    high = [i for i in ranked if i.risk_score >= config.RISK_ALERT_THRESHOLD]

    inst = db.get(Institution, 1)
    rows = parse_csv(config.SAMPLE_CSV.read_bytes())
    t = time.perf_counter()
    res = validate_rows(db, inst, rows)
    val_ms = (time.perf_counter() - t) * 1000
    planted_codes = {"APR-001", "APR-002", "APR-003", "APR-004", "APR-005", "APR-007", "DUP-001", "DUP-002",
                     "DUP-003", "INT-001", "INT-002", "CON-001", "CON-002", "CON-004", "CON-005", "CON-007"}
    found_codes = {f["code"] for r in res for f in r["findings"]}
    clean_rows = [r for r in res if not r["findings"]]
    db.rollback()

    out = {
        "dataset": {"institutions": summary["institutions"], "students": summary["students"],
                    "enrolments": summary["enrolments"]},
        "national_scan_seconds": round(scan_s, 2), "risk_scoring_seconds": round(score_s, 2),
        "scan_findings": scan["findings"],
        "dual_enrolment_recall": f"{ghost_hit}/{len(ghost)}",
        "identity_duplicate_recall": f"{ident_hit}/{len(ident)}",
        "risk_precision_at_k": f"{len(top_k & planted_insts)}/{k}",
        "high_risk_alerts_all_planted": all(i.id in planted_insts for i in high),
        "high_risk_alerts": len(high),
        "upload_rows": len(res), "upload_validation_ms": round(val_ms),
        "planted_defect_types_caught": f"{len(planted_codes & found_codes)}/{len(planted_codes)}",
        "upload_rows_clean": len(clean_rows),
    }
    db.close()
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
