"""Institution risk scoring.

Combines an unsupervised outlier model (Isolation Forest over per-institution
rates) with rule-based evidence, and explains every score with the features
that deviate most from peers. Scores prioritise review; they do not establish
wrongdoing.
"""
from collections import defaultdict

import numpy as np
from sklearn.ensemble import IsolationForest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import config
from .models import Enrolment, Finding, Institution, Programme, Student

# feature -> (explanation, peer comparison, minimum value worth reporting)
FEATURES = {
    "excess_admission_rate": ("Admissions beyond approved intake equal {v:.1%} of total intake",
                              "peer median {m:.1%}", 0.0),
    "supernumerary_share": ("Supernumerary admissions are {v:.1%} of intake", "peer median {m:.1%}", 0.12),
    "fn_share": ("FN/OCI/PIO admissions are {v:.1%} of intake", "peer median {m:.1%}", 0.05),
    "apaar_gap_rate": ("{v:.1%} of students lack a valid APAAR ID", "peer median {m:.1%}", 0.03),
    "dual_enrolment_rate": ("{v:.1%} of students are also active at another institution",
                            "peer median {m:.1%}", 0.03),
    "identity_dup_rate": ("{v:.1%} of students resemble a student enrolled elsewhere under a different "
                          "APAAR ID", "peer median {m:.1%}", 0.02),
    "late_admission_rate": ("{v:.1%} of admissions fall outside the admission window",
                            "peer median {m:.1%}", 0.05),
    "shared_contact_rate": ("{v:.1%} of students share a mobile or e-mail with many students elsewhere",
                            "peer median {m:.1%}", 0.02),
}
MIN_PEER_GROUP = 12  # smaller groups fall back to all institutions


def compute_features(db: Session) -> tuple[list[int], np.ndarray, dict]:
    insts = db.scalars(select(Institution.id)).all()
    progs = {p.id: p for p in db.scalars(select(Programme))}
    intake = defaultdict(int)
    for p in progs.values():
        intake[p.institution_id] += p.approved_intake
    within_by_prog, sn, fn, total, gap = (defaultdict(int) for _ in range(5))
    for inst_id, prog_id, seat, sn_type, apaar, consent, is_fn, is_oci in db.execute(
            select(Enrolment.institution_id, Enrolment.programme_id, Enrolment.seat_type,
                   Enrolment.supernumerary_type, Student.apaar_id, Student.apaar_consent,
                   Student.fn_status, Student.oci_status)
            .join(Student)
            .where(Enrolment.status == "ACTIVE", Enrolment.admission_year == config.ADMISSION_YEAR)):
        total[inst_id] += 1
        if seat == "WITHIN_INTAKE":
            within_by_prog[prog_id] += 1
        else:
            sn[inst_id] += 1
            if sn_type == "FN_OCI_PIO":
                fn[inst_id] += 1
        if not apaar and consent != "REFUSED" and not (is_fn or is_oci):
            gap[inst_id] += 1
    excess = defaultdict(int)
    for pid, n in within_by_prog.items():
        excess[progs[pid].institution_id] += max(0, n - progs[pid].approved_intake)
    per_rule = defaultdict(lambda: defaultdict(int))
    for inst_id, code, n in db.execute(
            select(Finding.institution_id, Finding.rule_code, func.count())
            .where(Finding.status == "OPEN").group_by(Finding.institution_id, Finding.rule_code)):
        per_rule[inst_id][code] = n

    X = []
    for i in insts:
        t, cap = max(total[i], 1), max(intake[i], 1)
        X.append([
            excess[i] / cap,
            sn[i] / cap,
            fn[i] / cap,
            (gap[i] + per_rule[i]["APR-003"]) / t,
            per_rule[i]["DUP-002"] / t,
            per_rule[i]["DUP-003"] / t,
            per_rule[i]["CON-006"] / t,
            per_rule[i]["DUP-004"] / t,
        ])
    return insts, np.array(X, dtype=float), per_rule


def score_institutions(db: Session) -> dict:
    ids, X, per_rule = compute_features(db)
    if len(ids) < 10:
        return {"scored": 0}
    model = IsolationForest(n_estimators=300, contamination=0.08, random_state=7).fit(X)
    raw = -model.score_samples(X)
    iso = (raw - raw.min()) / (raw.max() - raw.min() + 1e-9) * 100

    # Peers are institutions of the same type (engineering colleges against engineering colleges).
    types = dict(db.execute(select(Institution.id, Institution.inst_type)).all())
    groups: dict[str, list[int]] = defaultdict(list)
    for k, inst_id in enumerate(ids):
        groups[types[inst_id]].append(k)
    peer = {}
    for t, rows in groups.items():
        sub = X[rows] if len(rows) >= MIN_PEER_GROUP else X
        med = np.median(sub, axis=0)
        mad = np.median(np.abs(sub - med), axis=0) * 1.4826
        spread = np.where(mad > 1e-6, mad, sub.std(axis=0) + 1e-6)
        label = f"{t.lower()} peers" if len(rows) >= MIN_PEER_GROUP else "all institutions"
        for k in rows:
            peer[k] = (med, spread, label)
    names = list(FEATURES)

    totals = dict(db.execute(select(Enrolment.institution_id, func.count())
                             .where(Enrolment.status == "ACTIVE").group_by(Enrolment.institution_id)).all())
    flagged = dict(db.execute(
        select(Finding.institution_id, func.count(func.distinct(Finding.enrolment_id)))
        .where(Finding.status == "OPEN", Finding.enrolment_id.is_not(None), Finding.severity != "INFO")
        .group_by(Finding.institution_id)).all())

    for k, inst_id in enumerate(ids):
        med, spread, label = peer[k]
        z = (X[k] - med) / spread
        reasons = []
        for j in np.argsort(-z):
            text, peer_txt, floor = FEATURES[names[j]]
            hard_violation = names[j] == "excess_admission_rate" and X[k, j] > 0
            if (z[j] < 3 and not hard_violation) or X[k, j] <= floor:
                continue
            reasons.append({"feature": names[j], "value": round(float(X[k, j]), 4),
                            "peer_median": round(float(med[j]), 4), "z": round(float(min(z[j], 99)), 1),
                            "peers": label,
                            "text": text.format(v=X[k, j]) + f" ({peer_txt.format(m=med[j])}, {label})"})
            if len(reasons) == 3:
                break
        rules = per_rule[inst_id]
        rule_points = min(100.0, 45 * bool(rules["INT-001"]) + 25 * bool(rules["INT-002"])
                          + sum(min(r["z"], 20) * 3 for r in reasons))
        risk = round(0.5 * float(iso[k]) + 0.5 * rule_points, 1)
        if not reasons:
            risk = min(risk, 30.0)
        inst = db.get(Institution, inst_id)
        inst.risk_score = risk
        inst.risk_reasons = reasons
        t = totals.get(inst_id, 0)
        inst.quality_score = round(100 * (1 - flagged.get(inst_id, 0) / t), 1) if t else 100.0
    db.flush()
    return {"scored": len(ids)}
