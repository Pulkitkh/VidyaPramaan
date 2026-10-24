"""Shared test setup: one small synthetic dataset in an isolated temp directory, seeded once."""
import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="vp-test-"))
os.environ["VP_DATA_DIR"] = str(_tmp)
os.environ["VP_SAMPLE_CSV"] = str(_tmp / "sample.csv")
os.environ["VP_SEED_INSTITUTIONS"] = "60"
os.environ["VP_DEMO_MODE"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

from app import seed  # noqa: E402
from app.main import app  # noqa: E402

SUMMARY = seed.main(60)
client = TestClient(app)
client.__enter__()  # run the app's startup (issuer key check) once for the whole session


def login(username: str) -> dict:
    r = client.post("/api/auth/demo-login", json={"username": username})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}
