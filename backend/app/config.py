"""Runtime configuration and regulatory rule parameters.

Regulatory numbers are data, not code: they live in a versioned rules file per
academic year (app/rules/aicte_<year>.json), each value with its source and a
"verified" flag. AICTE changes these by handbook addendum or circular, so a new
year or a correction is a new file, not a code change.
"""
import json
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("VP_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

SAMPLE_CSV = Path(os.getenv("VP_SAMPLE_CSV", BASE_DIR.parent / "sample-data" / "demo_upload_btech_cse.csv"))
DATABASE_URL = os.getenv("VP_DATABASE_URL", f"sqlite:///{DATA_DIR / 'vidyapramaan.db'}")
# Signs login sessions. Set VP_SECRET_KEY in every deployment; without it a random key is generated
# per process (sessions then end on restart), so no usable default secret exists in the code.
SECRET_KEY_FROM_ENV = bool(os.getenv("VP_SECRET_KEY"))
SECRET_KEY = os.getenv("VP_SECRET_KEY") or secrets.token_urlsafe(32)
# Public address printed in certificate QR codes. Hosting platforms expose it automatically.
PUBLIC_BASE_URL = (os.getenv("VP_PUBLIC_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL")
                   or (f"https://{os.environ['SPACE_HOST']}" if os.getenv("SPACE_HOST") else "")
                   or "http://localhost:8000").rstrip("/")
APAAR_REGISTRY = os.getenv("VP_APAAR_REGISTRY", "mock")  # mock | digilocker
# Demo conveniences (one-click role sign-in, OTP shown on screen, reset and tamper simulation) are off
# unless explicitly enabled, so a production deployment cannot ship them by accident.
DEMO_MODE = os.getenv("VP_DEMO_MODE", "0") == "1"
# When set, resetting the shared public demo needs this PIN, so visitors cannot wipe it mid-evaluation.
DEMO_PIN = os.getenv("VP_DEMO_PIN", "")

RULES_DIR = Path(__file__).resolve().parent / "rules"
RULES_FILE = Path(os.getenv("VP_RULES_FILE", RULES_DIR / "aicte_2026_27.json"))
RULESET = json.loads(RULES_FILE.read_text())

CURRENT_ACADEMIC_YEAR = RULESET["academic_year"]
ADMISSION_YEAR = int(RULESET["admission_year"])
ADMISSION_WINDOW = tuple(RULESET["admission_window"])
RULESET_VERSION = RULESET["version"]
NEAR_CAP_WARNING = float(RULESET["near_cap_warning"])
SUPERNUMERARY = RULESET["supernumerary"]
SUPERNUMERARY_TYPES = tuple(SUPERNUMERARY)
AGE_LIMITS = {k: tuple(v) for k, v in RULESET["age_limits"].items()}


def sn_cap_fraction(sn_type: str, level: str) -> float:
    """Supernumerary cap as a fraction of approved intake for a programme level."""
    caps = SUPERNUMERARY[sn_type]["caps"]
    return float(caps.get(level, caps.get("UG", 0)))


RISK_ALERT_THRESHOLD = 70
