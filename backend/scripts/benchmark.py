"""Measure detection quality and speed on the synthetic dataset.

Ground truth comes from the seed: planted institutions are listed in
data/seed_summary.json, planted dual enrolments use roll-number sequence 900-949,
planted identity duplicates 950-999 and same-day twins (which must NOT be flagged) 600-699.
These are regression checks on planted cases, not accuracy on real data; the independent
estimate of identity-matching quality comes from scripts/identity_eval.py.
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
from app.validation import map_columns, parse_csv, validate_rows
from scripts import identity_eval


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
    twins = [e for e in enrols if 600 <= int(e.roll_no[-3:]) < 700]
    ghost_hit = sum((e.id, "DUP-002") in flagged for e in ghost)
    ident_hit = sum((e.id, "DUP-003") in flagged for e in ident)
    twin_flagged = sum((e.id, "DUP-003") in flagged for e in twins)
    clusters = {(f.evidence or {}).get("case") for f in db.scalars(select(Finding).where(
        Finding.status == "OPEN", Finding.rule_code == "DUP-004"))}
    ident_eval = identity_eval.main()

    ranked = db.scalars(select(Institution).order_by(Institution.risk_score.desc())).all()
    k = len(planted_insts)
    top_k = {i.id for i in ranked[:k]}
    high = [i for i in ranked if i.risk_score >= config.RISK_ALERT_THRESHOLD]

    inst = db.get(Institution, 1)
    rows, _, _ = map_columns(parse_csv(config.SAMPLE_CSV.read_bytes()))
    t = time.perf_counter()
    res = validate_rows(db, inst, rows)
    val_ms = (time.perf_counter() - t) * 1000
    planted_codes = {"APR-001", "APR-002", "APR-003", "APR-004", "APR-005", "APR-007", "DUP-001", "DUP-002",
                     "DUP-003", "INT-001", "INT-002", "INT-003", "CON-001", "CON-002", "CON-004", "CON-005",
                     "CON-007"}
    found_codes = {f["code"] for r in res for f in r["findings"]}
    clean_rows = [r for r in res if not [f for f in r["findings"] if f["code"] != "INT-003"]]
    db.rollback()

    out = {
        "dataset": {"institutions": summary["institutions"], "students": summary["students"],
                    "enrolments": summary["enrolments"]},
        "national_scan_seconds": round(scan_s, 2), "risk_scoring_seconds": round(score_s, 2),
        "scan_findings": scan["findings"],
        "dual_enrolment_recall": f"{ghost_hit}/{len(ghost)}",
        "identity_duplicate_recall": f"{ident_hit}/{len(ident)}",
        "twins_wrongly_flagged": f"{twin_flagged}/{len(twins)}",
        "shared_contact_clusters_found": f"{len(clusters)}/{len(summary['contact_clusters'])}",
        "identity_matching_labelled_pairs": {
            k: {m: {x: v[m][x] for x in ("pairs", "precision", "recall", "by_kind")}
                for m in ("current_matcher", "previous_matcher")} for k, v in ident_eval.items()},
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
