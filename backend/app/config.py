"""Runtime configuration and regulatory rule parameters.

Every regulatory number lives here so it can be changed without touching code.
The supernumerary caps below are DEMO values modelled on the AICTE Approval
Process Handbook (APH); verify them against the APH in force before any real use.
"""
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
SECRET_KEY = os.getenv("VP_SECRET_KEY") or secrets.token_urlsafe(32)
# Public address printed in certificate QR codes. Hosting platforms expose it automatically.
PUBLIC_BASE_URL = (os.getenv("VP_PUBLIC_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL")
                   or (f"https://{os.environ['SPACE_HOST']}" if os.getenv("SPACE_HOST") else "")
                   or "http://localhost:8000").rstrip("/")
APAAR_REGISTRY = os.getenv("VP_APAAR_REGISTRY", "mock")  # mock | digilocker
DEMO_MODE = os.getenv("VP_DEMO_MODE", "1") == "1"

CURRENT_ACADEMIC_YEAR = "2026-27"
ADMISSION_YEAR = 2026
ADMISSION_WINDOW = ("2026-06-01", "2026-09-30")

RULESET_VERSION = "aph-demo-2026.1"

# Supernumerary quotas as a fraction of approved intake (DEMO values, see module docstring).
SUPERNUMERARY_CAPS = {
    "FN_OCI_PIO": 0.15,  # Foreign Nationals / OCI / PIO / children of Indian workers in Gulf
    "TFW": 0.05,         # Tuition Fee Waiver
    "LATERAL": 0.10,     # Lateral entry into 2nd year
    "EWS": 0.10,         # Economically Weaker Section (where sanctioned as supernumerary)
}

# Plausible age at admission, by programme level.
AGE_LIMITS = {"UG": (16, 30), "PG": (20, 45), "DIPLOMA": (14, 30)}

RISK_ALERT_THRESHOLD = 70
