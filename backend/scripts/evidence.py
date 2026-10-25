"""Collect the engineering evidence quoted in the deck into docs/evidence.json.

Runs the test suite with coverage and reads the accessibility report written by e2e/accessibility.mjs.
Usage (from backend/): python -m scripts.evidence
"""
import json
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "coverage.json"
        run = subprocess.run([sys.executable, "-m", "pytest", "-q", "--cov=app", f"--cov-report=json:{report}"],
                             cwd=ROOT / "backend", capture_output=True, text=True)
        cov = json.loads(report.read_text())["totals"]
    last = run.stdout.strip().splitlines()[-1]
    a11y = json.loads((ROOT / "docs" / "accessibility_report.json").read_text())
    out = {
        "date": date.today().isoformat(),
        "tests": last,
        "tests_passed": run.returncode == 0,
        "coverage_percent": round(cov["percent_covered"]),
        "accessibility": {"standard": a11y["standard"], "screen_checks": a11y["screens"],
                          "violations": sum(len(r["violations"]) for r in a11y["results"])},
    }
    (ROOT / "docs" / "evidence.json").write_text(json.dumps(out, indent=1) + "\n")
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
