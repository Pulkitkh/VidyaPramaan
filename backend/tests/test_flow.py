"""End-to-end tests over a small synthetic dataset (isolated temp database)."""
import os
import tempfile
from pathlib import Path

import pytest

_tmp = Path(tempfile.mkdtemp(prefix="vp-test-"))
os.environ["VP_DATA_DIR"] = str(_tmp)
os.environ["VP_SAMPLE_CSV"] = str(_tmp / "sample.csv")
os.environ["VP_SEED_INSTITUTIONS"] = "60"

from fastapi.testclient import TestClient  # noqa: E402

from app import seed  # noqa: E402
from app.main import app  # noqa: E402

SUMMARY = seed.main(60)
client = TestClient(app)


def login(username: str) -> dict:
    r = client.post("/api/auth/demo-login", json={"username": username})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def inst():
    return login("inst.admin")


@pytest.fixture(scope="module")
def aicte():
    return login("aicte.admin")


@pytest.fixture(scope="module")
def batch(inst):
    with open(os.environ["VP_SAMPLE_CSV"], "rb") as fh:
        r = client.post("/api/institution/uploads", headers=inst, files={"file": ("cse.csv", fh, "text/csv")})
    assert r.status_code == 200, r.text
    return r.json()


def codes(batch) -> set[str]:
    return {f["code"] for row in batch["rows"] for f in row["findings"]}


def test_upload_flags_every_planted_defect(batch):
    expected = {"APR-001", "APR-002", "APR-003", "APR-004", "APR-005", "APR-007", "DUP-001", "DUP-002", "DUP-003",
                "INT-001", "INT-002", "CON-001", "CON-002", "CON-004", "CON-005", "CON-007"}
    assert expected <= codes(batch)
    assert batch["total_rows"] == 77
    assert batch["error_rows"] == 12


def test_intake_overflow_counts_seats(batch):
    seats = [f["evidence"]["seat_number"] for row in batch["rows"] for f in row["findings"] if f["code"] == "INT-001"]
    assert seats == [61, 62, 63]


def test_rbac_blocks_other_roles(batch):
    student = login("student.ananya")
    assert client.get("/api/dashboard/national", headers=student).status_code == 403
    assert client.post(f"/api/institution/uploads/{batch['id']}/commit", headers=login("aicte.admin")).status_code == 403


def test_commit_never_exceeds_intake(inst, batch):
    r = client.post(f"/api/institution/uploads/{batch['id']}/commit", headers=inst)
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 65
    ov = client.get("/api/institution/overview", headers=inst).json()
    cse = next(p for p in ov["ledger"] if p["code"] == "BTCSE")
    assert cse["within_intake"] == 60 and cse["excess"] == 0
    assert cse["supernumerary"]["TFW"]["used"] == 3
    assert client.post(f"/api/institution/uploads/{batch['id']}/commit", headers=inst).status_code == 409


def test_national_dashboard_and_risk(aicte):
    d = client.get("/api/dashboard/national", headers=aicte).json()
    assert d["kpis"]["institutions"] == 60
    assert d["kpis"]["dual_enrolments"] > 0
    assert d["top_risk"][0]["risk_score"] >= d["top_risk"][-1]["risk_score"]
    planted = {i for ids in SUMMARY["planted"].values() for i in ids}
    top = {i["id"] for i in d["top_risk"][:5]}
    assert len(top & planted) >= 4


def test_consent_flow_discloses_only_scope():
    verifier, student = login("hr.verifier"), login("student.ananya")
    rec = client.get("/api/me/record", headers=student).json()
    apaar = rec["student"]["apaar_id"]
    r = client.post("/api/verify/consent-requests", headers=verifier,
                    json={"apaar_id": apaar, "purpose": "Offer verification", "scope": ["enrolment_status", "programme"]})
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    assert client.get(f"/api/verify/consent-requests/{cid}/result", headers=verifier).json()["status"] == "PENDING"
    pending = next(c for c in client.get("/api/me/consents", headers=student).json() if c["id"] == cid)
    assert client.post(f"/api/me/consents/{cid}/decision", headers=student,
                       json={"decision": "APPROVE", "otp": "bad"}).status_code == 400
    client.post(f"/api/me/consents/{cid}/decision", headers=student,
                json={"decision": "APPROVE", "otp": pending["demo_otp"]}).raise_for_status()
    res = client.get(f"/api/verify/consent-requests/{cid}/result", headers=verifier).json()
    assert set(res["disclosed"]) == {"enrolment_status", "programme"}
    assert "institution" in res["withheld"]


def test_qr_token_verifies_and_detects_tampering():
    student = login("student.ananya")
    token = client.get("/api/me/record", headers=student).json()["credentials"][0]["token"]
    ok = client.post("/api/verify/token", json={"token": token}).json()
    assert ok["verdict"] == "VERIFIED"
    h, p, s = token.split(".")
    forged = ".".join([h, p[:-2] + ("A" if p[-2] != "A" else "B") + p[-1], s])
    assert client.post("/api/verify/token", json={"token": forged}).json()["verdict"] == "TAMPERED_OR_INVALID"


def test_certificate_pdf():
    student = login("student.ananya")
    token = student["Authorization"].split()[1]
    eid = client.get("/api/me/record", headers=student).json()["enrolments"][0]["id"]
    r = client.get(f"/api/enrolments/{eid}/certificate.pdf", params={"token": token})
    assert r.status_code == 200 and r.content[:4] == b"%PDF"


def test_audit_chain_detects_tampering(aicte):
    assert client.get("/api/audit/verify", headers=aicte).json()["valid"] is True
    client.post("/api/audit/tamper-demo", headers=aicte).raise_for_status()
    bad = client.get("/api/audit/verify", headers=aicte).json()
    assert bad["valid"] is False and bad["broken_at"]
    client.post("/api/audit/restore-demo", headers=aicte).raise_for_status()
    assert client.get("/api/audit/verify", headers=aicte).json()["valid"] is True


def test_reports(aicte):
    token = aicte["Authorization"].split()[1]
    assert client.get("/api/reports/excess-intake.csv", params={"token": token}).status_code == 200
    r = client.get("/api/reports/state-summary.xlsx", params={"token": token})
    assert r.status_code == 200 and r.content[:2] == b"PK"
