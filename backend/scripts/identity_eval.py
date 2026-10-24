"""Precision and recall of identity matching on a hand-labelled set of Indian name pairs.

The pairs in tests/data/identity_pairs.csv were written by hand and are independent of the synthetic
seed: real spelling variants of one person (label 1) and different people who share a date of birth
and a parent, mostly twins and common names (label 0). The earlier matcher (a plain fuzzy ratio with
fixed thresholds) is scored alongside, so the improvement is measured, not claimed.
Run from backend/:  python -m scripts.identity_eval
"""
import csv
import json
from datetime import date
from pathlib import Path

from rapidfuzz import fuzz

from app.matching import Person, same_person

DATA_DIR = Path(__file__).resolve().parents[1] / "tests" / "data"
# "development" was used while writing the matcher's spelling rules; "held_out" was written afterwards and
# scored once, so its numbers are the honest estimate.
SETS = {"development": DATA_DIR / "identity_pairs.csv", "held_out": DATA_DIR / "identity_pairs_holdout.csv"}


def _old_norm(name: str) -> str:
    tokens = "".join(c if c.isalpha() else " " for c in (name or "").lower()).split()
    return " ".join(t for t in tokens if len(t) > 1)


def old_matcher(a: Person, b: Person) -> bool:
    """The matcher this project used before (token_sort_ratio >= 88 on names, >= 85 on fathers, exact DOB)."""
    return (a.dob == b.dob and a.gender == b.gender
            and fuzz.token_sort_ratio(_old_norm(a.name), _old_norm(b.name)) >= 88
            and fuzz.token_sort_ratio(_old_norm(a.father_name), _old_norm(b.father_name)) >= 85)


def load(path: Path) -> list[dict]:
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    for r in rows:
        r["a"] = Person(r["name_a"], date.fromisoformat(r["dob_a"]), r["gender"], r["parent_a"])
        r["b"] = Person(r["name_b"], date.fromisoformat(r["dob_b"]), r["gender"], r["parent_b"])
        r["label"] = int(r["label"])
    return rows


def score(rows: list[dict], fn) -> dict:
    tp = sum(1 for r in rows if r["label"] and fn(r["a"], r["b"]))
    fp = sum(1 for r in rows if not r["label"] and fn(r["a"], r["b"]))
    fn_ = sum(1 for r in rows if r["label"] and not fn(r["a"], r["b"]))
    tn = sum(1 for r in rows if not r["label"] and not fn(r["a"], r["b"]))
    by_kind = {}
    for kind in sorted({r["kind"] for r in rows}):
        sub = [r for r in rows if r["kind"] == kind]
        flagged = sum(1 for r in sub if fn(r["a"], r["b"]))
        by_kind[kind] = f"{flagged}/{len(sub)} flagged"
    return {"pairs": len(rows), "true_positive": tp, "false_positive": fp, "false_negative": fn_, "true_negative": tn,
            "precision": round(tp / (tp + fp), 3) if tp + fp else None, "recall": round(tp / (tp + fn_), 3),
            "by_kind": by_kind}


def evaluate(rows: list[dict]) -> dict:
    new = lambda a, b: same_person(a, b).match  # noqa: E731
    misses = [f"{r['name_a']} / {r['name_b']} ({r['note']})" for r in rows if r["label"] and not new(r["a"], r["b"])]
    false_alarms = [f"{r['name_a']} / {r['name_b']} ({r['note']})" for r in rows if not r["label"] and new(r["a"], r["b"])]
    return {"current_matcher": score(rows, new), "previous_matcher": score(rows, old_matcher),
            "current_misses": misses, "current_false_alarms": false_alarms}


def main() -> dict:
    return {name: evaluate(load(path)) for name, path in SETS.items()}


if __name__ == "__main__":
    print(json.dumps(main(), indent=1, ensure_ascii=False))
