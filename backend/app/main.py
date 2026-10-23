"""Vidya Pramaan API: APAAR-linked student data, validation, monitoring and verification."""
import csv
import io
import json
import random
from datetime import timedelta
from pathlib import Path

from fastapi import Body, Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from openpyxl import Workbook
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from . import audit, config, events, services
from .anomaly import score_institutions
from .apaar_registry import is_valid_format, mask
from .auth import User, current_user, issue_token, parse_token, require
from .certificates import qr_png, render_certificate, verify_url
from .credentials import build_credential, public_jwk, verify_compact, verify_vc
from .db import Base, engine, get_db
from .models import (AuditEvent, ConsentRequest, Credential, Enrolment, Finding, Institution, Programme,
                     Student, UploadBatch, VerificationLog, now)
from .scan import run_scan
from .validation import COLUMNS, ENUMS, RULES, parse_csv, parse_xlsx

Base.metadata.create_all(engine)
app = FastAPI(title="Vidya Pramaan API", version="0.1.0",
              description="APAAR ID-based student data management and verification (SIH26263 prototype). "
                          "All data is synthetic.")

AICTE = ("AICTE_ADMIN", "AUDITOR")
SCOPE_FIELDS = {"enrolment_status", "programme", "institution", "admission_year", "name", "year_of_study"}


# --------------------------------------------------------------------------- auth
def demo_users(db: Session) -> list[User]:
    student = db.scalars(select(Student).where(Student.name == "Ananya Kulkarni")).first()
    return [
        User("aicte.admin", "AICTE_ADMIN", "AICTE Regulation Bureau (officer)"),
        User("inst.admin", "INSTITUTION_ADMIN", "Demo Institute of Technology, Pune", institution_id=1),
        User("hr.verifier", "VERIFIER", "Acme Technologies (employer)",
             org="Acme Technologies Pvt Ltd (demo employer)"),
        User("student.ananya", "STUDENT", "Ananya Kulkarni (student)", student_id=student.id if student else None),
        User("auditor", "AUDITOR", "Internal auditor (read-only)"),
    ]


@app.get("/api/auth/demo-users")
def list_demo_users(db: Session = Depends(get_db)):
    return [u.__dict__ for u in demo_users(db)]


@app.post("/api/auth/demo-login")
def demo_login(username: str = Body(embed=True), db: Session = Depends(get_db)):
    user = next((u for u in demo_users(db) if u.username == username), None)
    if not user:
        raise HTTPException(404, "Unknown demo user")
    audit.record(db, user.username, user.role, "LOGIN", "session", user.username)
    db.commit()
    return {"token": issue_token(user), "user": user.__dict__}


@app.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    return user.__dict__


# --------------------------------------------------------------------------- meta
@app.get("/api/meta")
def meta():
    return {"rules": {k: {"severity": v[0], "title": v[1]} for k, v in RULES.items()},
            "ruleset_version": config.RULESET_VERSION, "supernumerary_caps": config.SUPERNUMERARY_CAPS,
            "admission_window": config.ADMISSION_WINDOW, "academic_year": config.CURRENT_ACADEMIC_YEAR,
            "apaar_registry": config.APAAR_REGISTRY, "columns": COLUMNS, "demo_mode": config.DEMO_MODE}


@app.get("/api/events")
async def sse(token: str):
    parse_token(token)
    return StreamingResponse(events.stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# --------------------------------------------------------------------------- AICTE monitoring
@app.get("/api/dashboard/national")
def dashboard(db: Session = Depends(get_db), _: User = Depends(require(*AICTE))):
    return services.national_dashboard(db)


@app.get("/api/institutions")
def institutions(q: str = "", state: str = "", sort: str = "risk", limit: int = 50, offset: int = 0,
                 db: Session = Depends(get_db), _: User = Depends(require(*AICTE))):
    stmt = select(Institution)
    if q:
        stmt = stmt.where(or_(Institution.name.ilike(f"%{q}%"), Institution.aicte_pid.ilike(f"%{q}%")))
    if state:
        stmt = stmt.where(Institution.state == state)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    order = {"risk": Institution.risk_score.desc(), "quality": Institution.quality_score.asc(),
             "name": Institution.name.asc()}.get(sort, Institution.risk_score.desc())
    rows = db.scalars(stmt.order_by(order).limit(limit).offset(offset)).all()
    ids = [i.id for i in rows]
    intake = dict(db.execute(select(Programme.institution_id, func.sum(Programme.approved_intake))
                             .where(Programme.institution_id.in_(ids)).group_by(Programme.institution_id)).all())
    enrolled = dict(db.execute(select(Enrolment.institution_id, func.count())
                               .where(Enrolment.institution_id.in_(ids), Enrolment.status == "ACTIVE")
                               .group_by(Enrolment.institution_id)).all())
    open_f = dict(db.execute(select(Finding.institution_id, func.count())
                             .where(Finding.institution_id.in_(ids), Finding.status == "OPEN")
                             .group_by(Finding.institution_id)).all())
    return {"total": total, "items": [
        {"id": i.id, "name": i.name, "aicte_pid": i.aicte_pid, "state": i.state, "city": i.city,
         "region": i.region, "type": i.inst_type, "risk_score": i.risk_score, "quality_score": i.quality_score,
         "reasons": i.risk_reasons, "intake": intake.get(i.id, 0), "enrolled": enrolled.get(i.id, 0),
         "open_findings": open_f.get(i.id, 0)} for i in rows]}


@app.get("/api/institutions/{inst_id}")
def institution_detail(inst_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role not in AICTE and user.institution_id != inst_id:
        raise HTTPException(403, "Not your institution")
    inst = db.get(Institution, inst_id) or _404("Institution")
    by_rule = dict(db.execute(select(Finding.rule_code, func.count())
                              .where(Finding.institution_id == inst_id, Finding.status == "OPEN")
                              .group_by(Finding.rule_code)).all())
    batches = db.scalars(select(UploadBatch).where(UploadBatch.institution_id == inst_id)
                         .order_by(UploadBatch.id.desc()).limit(10)).all()
    return {"id": inst.id, "name": inst.name, "aicte_pid": inst.aicte_pid, "state": inst.state,
            "city": inst.city, "region": inst.region, "type": inst.inst_type, "risk_score": inst.risk_score,
            "quality_score": inst.quality_score, "reasons": inst.risk_reasons,
            "ledger": services.programme_ledger(db, inst_id), "findings_by_rule": by_rule,
            "batches": [_batch_summary(b) for b in batches]}


@app.get("/api/findings")
def findings(institution_id: int | None = None, rule: str = "", severity: str = "", status: str = "OPEN",
             limit: int = 50, offset: int = 0, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role == "INSTITUTION_ADMIN":
        institution_id = user.institution_id
    elif user.role not in AICTE:
        raise HTTPException(403, "Not allowed")
    stmt = select(Finding)
    if institution_id:
        stmt = stmt.where(Finding.institution_id == institution_id)
    if rule:
        stmt = stmt.where(Finding.rule_code == rule)
    if severity:
        stmt = stmt.where(Finding.severity == severity)
    if status:
        stmt = stmt.where(Finding.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(Finding.severity.asc(), Finding.id.desc()).limit(limit).offset(offset)).all()
    names = dict(db.execute(select(Institution.id, Institution.name)).all())
    return {"total": total, "items": [services.finding_dict(f, names) for f in rows]}


@app.get("/api/findings/{fid}")
def finding_detail(fid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    f = db.get(Finding, fid) or _404("Finding")
    if user.role not in AICTE and f.institution_id != user.institution_id:
        raise HTTPException(403, "Not allowed")
    names = dict(db.execute(select(Institution.id, Institution.name)).all())
    out = services.finding_dict(f, names)
    if f.enrolment_id:
        e = db.get(Enrolment, f.enrolment_id)
        out["record"] = {"student": services.student_public(e.student), "enrolment": services.enrolment_dict(e)}
        if f.rule_code in ("DUP-002", "DUP-003") and f.related_institution_id:
            other = _counterpart(db, e, f)
            if other:
                out["counterpart"] = {"student": services.student_public(other.student),
                                      "enrolment": services.enrolment_dict(other)}
    return out


def _counterpart(db: Session, e: Enrolment, f: Finding) -> Enrolment | None:
    q = select(Enrolment).where(Enrolment.institution_id == f.related_institution_id, Enrolment.status == "ACTIVE")
    if f.rule_code == "DUP-002":
        return db.scalars(q.where(Enrolment.student_id == e.student_id)).first()
    cands = db.scalars(q.join(Student).where(Student.dob == e.student.dob, Student.gender == e.student.gender)).all()
    from rapidfuzz import fuzz
    from .validation import norm_name
    return max(cands, key=lambda c: fuzz.token_sort_ratio(norm_name(c.student.name), norm_name(e.student.name)),
               default=None)


class Decision(BaseModel):
    decision: str
    note: str = ""


@app.post("/api/findings/{fid}/decision")
def decide(fid: int, body: Decision, db: Session = Depends(get_db), user: User = Depends(require("AICTE_ADMIN"))):
    f = db.get(Finding, fid) or _404("Finding")
    if body.decision not in ("RESOLVED", "DISMISSED", "ESCALATED"):
        raise HTTPException(400, "decision must be RESOLVED, DISMISSED or ESCALATED")
    f.status, f.resolution_note = body.decision, body.note
    audit.record(db, user.username, user.role, f"FINDING_{body.decision}", "finding", f.id,
                 {"rule": f.rule_code, "institution_id": f.institution_id, "note": body.note})
    db.commit()
    return services.finding_dict(f)


@app.post("/api/scan")
def scan(db: Session = Depends(get_db), user: User = Depends(require("AICTE_ADMIN"))):
    result = run_scan(db)
    score_institutions(db)
    audit.record(db, user.username, user.role, "NATIONAL_SCAN", "dataset", "national", result)
    db.commit()
    events.publish("scan", result)
    return result


@app.get("/api/aicte/students/{apaar_id}")
def statutory_lookup(apaar_id: str, purpose: str = Query(min_length=5), db: Session = Depends(get_db),
                     user: User = Depends(require("AICTE_ADMIN"))):
    s = db.scalars(select(Student).where(Student.apaar_id == apaar_id)).first() or _404("Student")
    enrols = db.scalars(select(Enrolment).where(Enrolment.student_id == s.id)).all()
    db.add(VerificationLog(student_id=s.id, verifier_org="AICTE", basis="STATUTORY", purpose=purpose,
                           disclosed={"fields": "full record"}))
    audit.record(db, user.username, user.role, "STATUTORY_LOOKUP", "student", mask(s.apaar_id), {"purpose": purpose})
    db.commit()
    return {"student": services.student_public(s), "enrolments": [services.enrolment_dict(e) for e in enrols]}


# --------------------------------------------------------------------------- institution
def _my_inst(db: Session, user: User) -> Institution:
    if not user.institution_id:
        raise HTTPException(403, "Institution users only")
    return db.get(Institution, user.institution_id)


def _batch_summary(b: UploadBatch) -> dict:
    return {"id": b.id, "filename": b.filename, "source": b.source, "uploaded_by": b.uploaded_by,
            "created_at": b.created_at, "status": b.status, "total_rows": b.total_rows,
            "error_rows": b.error_rows, "warning_rows": b.warning_rows, "committed_rows": b.committed_rows}


@app.get("/api/institution/overview")
def inst_overview(db: Session = Depends(get_db), user: User = Depends(require("INSTITUTION_ADMIN"))):
    return institution_detail(_my_inst(db, user).id, db, user)


@app.get("/api/institution/template.csv")
def template():
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS)
    w.writeheader()
    w.writerow({"apaar_id": "123456789012", "apaar_consent": "GIVEN", "roll_no": "0001BTCSE26001",
                "name": "Student Name", "dob": "2008-01-31", "gender": "F", "category": "GEN",
                "father_name": "Father Name", "programme_code": "BTCSE", "year_of_study": 1,
                "admission_type": "REGULAR", "quota": "STATE_CAP", "nationality": "Indian", "fn_status": "N",
                "oci_status": "N", "oci_card_no": "", "passport_no": "", "nri_status": "N", "nri_country": "",
                "pwd": "N", "admission_date": "2026-08-01"})
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=student_upload_template.csv"})


@app.get("/api/institution/template.xlsx")
def template_xlsx():
    """Excel template with drop-down lists for coded columns, for institutions that work in Excel."""
    from openpyxl.worksheet.datavalidation import DataValidation
    wb = Workbook()
    ws = wb.active
    ws.title = "Students"
    ws.append(COLUMNS)
    ws.append(["123456789012", "GIVEN", "0001BTCSE26001", "Student Name", "2008-01-31", "F", "GEN", "Father Name",
               "BTCSE", 1, "REGULAR", "STATE_CAP", "Indian", "N", "N", "", "", "N", "", "N", "2026-08-01"])
    yes_no = {"fn_status", "oci_status", "nri_status", "pwd"}
    for idx, col in enumerate(COLUMNS, start=1):
        letter = ws.cell(row=1, column=idx).column_letter
        ws.column_dimensions[letter].width = max(12, len(col) + 2)
        choices = sorted(ENUMS[col]) if col in ENUMS else ["Y", "N"] if col in yes_no else None
        if choices:
            dv = DataValidation(type="list", formula1='"' + ",".join(choices) + '"', allow_blank=True)
            ws.add_data_validation(dv)
            dv.add(f"{letter}2:{letter}5000")
        if col in ("apaar_id", "roll_no", "dob", "admission_date"):
            for r in range(2, 5001):
                ws.cell(row=r, column=idx).number_format = "@"  # keep IDs and dates as text
    ws.freeze_panes = "A2"
    buf = io.BytesIO()
    wb.save(buf)
    return Response(buf.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": "attachment; filename=student_upload_template.xlsx"})


@app.get("/api/institution/sample.csv")
def sample_csv():
    return FileResponse(config.SAMPLE_CSV, media_type="text/csv", filename=config.SAMPLE_CSV.name)


@app.post("/api/institution/uploads")
async def upload(file: UploadFile = File(...), db: Session = Depends(get_db),
                 user: User = Depends(require("INSTITUTION_ADMIN"))):
    content = await file.read()
    if len(content) > 10_000_000:
        raise HTTPException(413, "File too large for synchronous validation; use the bulk API")
    name = (file.filename or "").lower()
    try:
        rows = parse_xlsx(content) if name.endswith((".xlsx", ".xlsm")) else parse_csv(content)
    except UnicodeDecodeError:
        raise HTTPException(400, "CSV files must be UTF-8. Excel users can upload the .xlsx directly.")
    except Exception:
        raise HTTPException(400, "Could not read the file. Use the CSV or Excel template.")
    if not rows:
        raise HTTPException(400, "No rows found")
    batch = services.create_batch(db, _my_inst(db, user), rows, file.filename or "upload.csv", user)
    db.commit()
    return {**_batch_summary(batch), "rows": batch.row_results}


@app.get("/api/institution/uploads")
def uploads(db: Session = Depends(get_db), user: User = Depends(require("INSTITUTION_ADMIN"))):
    rows = db.scalars(select(UploadBatch).where(UploadBatch.institution_id == user.institution_id)
                      .order_by(UploadBatch.id.desc())).all()
    return [_batch_summary(b) for b in rows]


@app.get("/api/institution/uploads/{bid}")
def upload_detail(bid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    b = db.get(UploadBatch, bid) or _404("Batch")
    if user.role not in AICTE and b.institution_id != user.institution_id:
        raise HTTPException(403, "Not allowed")
    return {**_batch_summary(b), "rows": b.row_results}


@app.post("/api/institution/uploads/{bid}/commit")
def commit(bid: int, db: Session = Depends(get_db), user: User = Depends(require("INSTITUTION_ADMIN"))):
    b = db.get(UploadBatch, bid) or _404("Batch")
    if b.institution_id != user.institution_id:
        raise HTTPException(403, "Not your batch")
    if b.status != "VALIDATED":
        raise HTTPException(409, f"Batch already {b.status}")
    result = services.commit_batch(db, b, user)
    db.commit()
    inst = db.get(Institution, b.institution_id)
    events.publish("batch_committed", {"institution": inst.name, "institution_id": inst.id, **result,
                                       "risk_score": inst.risk_score})
    return {**_batch_summary(b), **result}


@app.get("/api/institution/students")
def inst_students(q: str = "", limit: int = 50, db: Session = Depends(get_db),
                  user: User = Depends(require("INSTITUTION_ADMIN"))):
    stmt = select(Enrolment).join(Student).where(Enrolment.institution_id == user.institution_id)
    if q:
        stmt = stmt.where(or_(Student.name.ilike(f"%{q}%"), Enrolment.roll_no.ilike(f"%{q}%"),
                              Student.apaar_id.ilike(f"%{q}%")))
    rows = db.scalars(stmt.order_by(Enrolment.id.desc()).limit(limit)).all()
    return [{"student": services.student_public(e.student, reveal=True), "enrolment": services.enrolment_dict(e)}
            for e in rows]


# --------------------------------------------------------------------------- ERP / system integration API
@app.post("/api/v1/students:validate", tags=["integration"])
def api_validate(rows: list[dict] = Body(...), db: Session = Depends(get_db),
                 user: User = Depends(require("INSTITUTION_ADMIN"))):
    """Dry-run validation for institutional ERPs; nothing is stored."""
    from .validation import validate_rows
    return validate_rows(db, _my_inst(db, user), rows)


@app.post("/api/v1/students:submit", tags=["integration"])
def api_submit(rows: list[dict] = Body(...), commit_now: bool = True, db: Session = Depends(get_db),
               user: User = Depends(require("INSTITUTION_ADMIN"))):
    """Validate and (optionally) commit a JSON batch in one call."""
    batch = services.create_batch(db, _my_inst(db, user), rows, "api-submission", user, source="API")
    result = services.commit_batch(db, batch, user) if commit_now else {}
    db.commit()
    return {**_batch_summary(batch), **result, "rows": batch.row_results}


@app.get("/api/v1/certificate-data/{enrolment_id}", tags=["integration"])
def certificate_data(enrolment_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Fields a degree-awarding body needs to print APAAR ID + student ID + verification QR."""
    e = _authorised_enrolment(db, enrolment_id, user)
    cred = _ensure_credential(db, e, user)
    db.commit()
    return {"apaar_id": e.student.apaar_id, "provisional_id": e.student.provisional_id, "student_id": e.roll_no,
            "name": e.student.name, "programme": e.programme.name, "institution": e.institution.name,
            "qr_payload": verify_url(cred.token), "credential_id": cred.id}


# --------------------------------------------------------------------------- credentials & certificates
def _authorised_enrolment(db: Session, enrolment_id: int, user: User) -> Enrolment:
    e = db.get(Enrolment, enrolment_id) or _404("Enrolment")
    ok = (user.role in AICTE or (user.role == "INSTITUTION_ADMIN" and e.institution_id == user.institution_id)
          or (user.role == "STUDENT" and e.student_id == user.student_id))
    if not ok:
        raise HTTPException(403, "Not allowed")
    return e


def _ensure_credential(db: Session, e: Enrolment, user: User) -> Credential:
    cred = db.scalars(select(Credential).where(Credential.enrolment_id == e.id, Credential.status == "ACTIVE")).first()
    if cred:
        return cred
    cred_id, vc, token = build_credential(e.student, e)
    cred = Credential(id=cred_id, student_id=e.student_id, enrolment_id=e.id, vc=vc, token=token)
    db.add(cred)
    audit.record(db, user.username, user.role, "CREDENTIAL_ISSUED", "credential", cred_id, {"enrolment": e.id})
    return cred


@app.get("/api/enrolments/{enrolment_id}/certificate.pdf")
def certificate(enrolment_id: int, token: str = "", db: Session = Depends(get_db)):
    """Token is passed as a query parameter so the PDF can open in a new browser tab."""
    user = _require_token(token, ("AICTE_ADMIN", "AUDITOR", "INSTITUTION_ADMIN", "STUDENT"))
    e = _authorised_enrolment(db, enrolment_id, user)
    cred = _ensure_credential(db, e, user)
    db.commit()
    pdf = render_certificate(e.student, e, cred.token)
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f"inline; filename=certificate_{e.roll_no}.pdf"})


@app.get("/api/credentials/{cred_id}/qr.png")
def credential_qr(cred_id: str, db: Session = Depends(get_db)):
    cred = db.get(Credential, cred_id) or _404("Credential")
    return Response(qr_png(verify_url(cred.token)), media_type="image/png")


@app.get("/api/credentials/{cred_id}/status")
def credential_status(cred_id: str, db: Session = Depends(get_db)):
    cred = db.get(Credential, cred_id) or _404("Credential")
    e = db.get(Enrolment, cred.enrolment_id)
    return {"id": cred.id, "status": cred.status, "enrolment_status": e.status, "checked_at": now()}


@app.get("/api/issuer/jwk")
def issuer_key():
    return public_jwk()


@app.post("/api/verify/token")
def verify_token(token: str = Body(embed=True), db: Session = Depends(get_db)):
    """Public: verify a QR token. Signature is checked offline; status is checked live."""
    valid, claims = verify_compact(token)
    out = {"signature_valid": valid, "claims": claims, "issuer": public_jwk()["kid"]}
    if valid and claims:
        cred = db.get(Credential, claims.get("cid"))
        out["registry_status"] = cred.status if cred else "UNKNOWN"
        if cred:
            e = db.get(Enrolment, cred.enrolment_id)
            out["enrolment_status_now"] = e.status
            db.add(VerificationLog(student_id=cred.student_id, verifier_org="Public QR verification",
                                   basis="CREDENTIAL", purpose="QR scan", disclosed=claims))
            db.commit()
    out["verdict"] = ("VERIFIED" if valid and out.get("registry_status") == "ACTIVE"
                      else "REVOKED" if valid else "TAMPERED_OR_INVALID")
    return out


@app.post("/api/verify/vc")
def verify_full_vc(vc: dict = Body(...)):
    return {"signature_valid": verify_vc(vc), "id": vc.get("id"), "issuer": (vc.get("issuer") or {}).get("id")}


# --------------------------------------------------------------------------- consent-based verification
class ConsentIn(BaseModel):
    apaar_id: str
    purpose: str
    scope: list[str]


@app.post("/api/verify/consent-requests")
def request_consent(body: ConsentIn, db: Session = Depends(get_db), user: User = Depends(require("VERIFIER"))):
    if not is_valid_format(body.apaar_id):
        raise HTTPException(400, "APAAR ID must be 12 digits")
    bad = set(body.scope) - SCOPE_FIELDS
    if bad or not body.scope:
        raise HTTPException(400, f"Scope must be a subset of {sorted(SCOPE_FIELDS)}")
    s = db.scalars(select(Student).where(Student.apaar_id == body.apaar_id)).first()
    if not s:
        raise HTTPException(404, "No student record for this APAAR ID")
    c = ConsentRequest(student_id=s.id, verifier_org=user.org or user.display_name, verifier_user=user.username,
                       purpose=body.purpose, scope=body.scope, otp=f"{random.randint(0, 999999):06d}",
                       expires_at=now() + timedelta(hours=24))
    db.add(c)
    db.flush()
    audit.record(db, user.username, user.role, "CONSENT_REQUESTED", "consent", c.id,
                 {"apaar": mask(body.apaar_id), "purpose": body.purpose, "scope": body.scope})
    db.commit()
    events.publish("consent_requested", {"consent_id": c.id, "student_id": s.id})
    return _consent_dict(c, show_otp=False)


@app.get("/api/verify/consent-requests")
def my_requests(db: Session = Depends(get_db), user: User = Depends(require("VERIFIER"))):
    rows = db.scalars(select(ConsentRequest).where(ConsentRequest.verifier_user == user.username)
                      .order_by(ConsentRequest.id.desc())).all()
    return [_consent_dict(c, show_otp=False) for c in rows]


@app.get("/api/verify/consent-requests/{cid}/result")
def consent_result(cid: int, db: Session = Depends(get_db), user: User = Depends(require("VERIFIER"))):
    c = db.get(ConsentRequest, cid) or _404("Consent")
    if c.verifier_user != user.username:
        raise HTTPException(403, "Not your request")
    if c.status != "APPROVED":
        return {"status": c.status, "disclosed": None}
    if c.expires_at < now():
        c.status = "EXPIRED"
        db.commit()
        return {"status": "EXPIRED", "disclosed": None}
    e = db.scalars(select(Enrolment).where(Enrolment.student_id == c.student_id)
                   .order_by(Enrolment.id.desc())).first()
    full = {"enrolment_status": e.status if e else "NOT_ENROLLED", "programme": e.programme.name if e else None,
            "institution": e.institution.name if e else None, "admission_year": e.admission_year if e else None,
            "name": db.get(Student, c.student_id).name, "year_of_study": e.year_of_study if e else None}
    disclosed = {k: full[k] for k in c.scope}
    db.add(VerificationLog(student_id=c.student_id, consent_id=c.id, verifier_org=c.verifier_org,
                           basis="CONSENT", purpose=c.purpose, disclosed=disclosed))
    audit.record(db, user.username, user.role, "VERIFICATION_DISCLOSED", "consent", c.id, {"fields": c.scope})
    db.commit()
    return {"status": "APPROVED", "disclosed": disclosed, "withheld": sorted(SCOPE_FIELDS - set(c.scope)),
            "consent_expires_at": c.expires_at}


def _consent_dict(c: ConsentRequest, show_otp: bool) -> dict:
    d = {"id": c.id, "verifier_org": c.verifier_org, "purpose": c.purpose, "scope": c.scope, "status": c.status,
         "created_at": c.created_at, "expires_at": c.expires_at, "decided_at": c.decided_at}
    if show_otp:
        d["demo_otp"] = c.otp  # in production the OTP goes to the student's registered mobile / DigiLocker
    return d


# --------------------------------------------------------------------------- student self-service
@app.get("/api/me/record")
def my_record(db: Session = Depends(get_db), user: User = Depends(require("STUDENT"))):
    s = db.get(Student, user.student_id) or _404("Student")
    enrols = db.scalars(select(Enrolment).where(Enrolment.student_id == s.id)).all()
    creds = db.scalars(select(Credential).where(Credential.student_id == s.id)).all()
    logs = db.scalars(select(VerificationLog).where(VerificationLog.student_id == s.id)
                      .order_by(VerificationLog.id.desc())).all()
    return {"student": services.student_public(s, reveal=True),
            "enrolments": [services.enrolment_dict(e) for e in enrols],
            "credentials": [{"id": c.id, "status": c.status, "issued_at": c.issued_at, "enrolment_id": c.enrolment_id,
                             "vc": c.vc, "token": c.token, "verify_url": verify_url(c.token)} for c in creds],
            "access_log": [{"id": l.id, "verifier_org": l.verifier_org, "basis": l.basis, "purpose": l.purpose,
                            "disclosed": l.disclosed, "at": l.created_at} for l in logs]}


@app.get("/api/me/consents")
def my_consents(db: Session = Depends(get_db), user: User = Depends(require("STUDENT"))):
    rows = db.scalars(select(ConsentRequest).where(ConsentRequest.student_id == user.student_id)
                      .order_by(ConsentRequest.id.desc())).all()
    return [_consent_dict(c, show_otp=config.DEMO_MODE and c.status == "PENDING") for c in rows]


class ConsentDecision(BaseModel):
    decision: str
    otp: str = ""


@app.post("/api/me/consents/{cid}/decision")
def decide_consent(cid: int, body: ConsentDecision, db: Session = Depends(get_db),
                   user: User = Depends(require("STUDENT"))):
    c = db.get(ConsentRequest, cid) or _404("Consent")
    if c.student_id != user.student_id:
        raise HTTPException(403, "Not your consent request")
    if c.status != "PENDING":
        raise HTTPException(409, f"Already {c.status}")
    if body.decision == "APPROVE":
        if body.otp != c.otp:
            raise HTTPException(400, "Incorrect OTP")
        c.status = "APPROVED"
    elif body.decision == "DENY":
        c.status = "DENIED"
    else:
        raise HTTPException(400, "decision must be APPROVE or DENY")
    c.decided_at = now()
    audit.record(db, user.username, user.role, f"CONSENT_{c.status}", "consent", c.id,
                 {"verifier": c.verifier_org, "scope": c.scope})
    db.commit()
    events.publish("consent_decided", {"consent_id": c.id, "status": c.status})
    return _consent_dict(c, show_otp=False)


@app.post("/api/me/consents/{cid}/revoke")
def revoke_consent(cid: int, db: Session = Depends(get_db), user: User = Depends(require("STUDENT"))):
    c = db.get(ConsentRequest, cid) or _404("Consent")
    if c.student_id != user.student_id:
        raise HTTPException(403, "Not your consent request")
    c.status = "REVOKED"
    audit.record(db, user.username, user.role, "CONSENT_REVOKED", "consent", c.id, {})
    db.commit()
    return _consent_dict(c, show_otp=False)


# --------------------------------------------------------------------------- audit
@app.get("/api/audit")
def audit_log(limit: int = 50, offset: int = 0, action: str = "", db: Session = Depends(get_db),
              _: User = Depends(require(*AICTE))):
    stmt = select(AuditEvent)
    if action:
        stmt = stmt.where(AuditEvent.action == action)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(AuditEvent.id.desc()).limit(limit).offset(offset)).all()
    return {"total": total, "items": [{"id": a.id, "ts": a.ts, "actor": a.actor, "role": a.role, "action": a.action,
                                       "entity": a.entity, "entity_id": a.entity_id, "details": a.details,
                                       "prev_hash": a.prev_hash, "hash": a.hash} for a in rows]}


@app.get("/api/audit/verify")
def audit_verify(db: Session = Depends(get_db), _: User = Depends(require(*AICTE))):
    return audit.verify_chain(db)


TAMPER_FILE = config.DATA_DIR / "tamper_demo.json"


@app.post("/api/audit/tamper-demo")
def tamper(db: Session = Depends(get_db), _: User = Depends(require("AICTE_ADMIN"))):
    """DEMO ONLY: silently edit an old audit row (as a rogue DB admin would) to show detection."""
    if not config.DEMO_MODE:
        raise HTTPException(404)
    ev = db.scalars(select(AuditEvent).where(AuditEvent.action == "UPLOAD_COMMITTED")
                    .order_by(AuditEvent.id)).first() or db.scalars(select(AuditEvent).order_by(AuditEvent.id)
                                                                   .offset(1)).first()
    TAMPER_FILE.write_text(json.dumps({"id": ev.id, "details": ev.details}))
    ev.details = {**ev.details, "rejected": 0, "note": "edited directly in the database"}
    db.commit()
    return {"tampered_event": ev.id}


@app.post("/api/audit/restore-demo")
def restore(db: Session = Depends(get_db), _: User = Depends(require("AICTE_ADMIN"))):
    if not TAMPER_FILE.exists():
        return {"restored": None}
    data = json.loads(TAMPER_FILE.read_text())
    ev = db.get(AuditEvent, data["id"])
    ev.details = data["details"]
    db.commit()
    TAMPER_FILE.unlink()
    return {"restored": ev.id}


@app.post("/api/demo/reset")
def demo_reset(db: Session = Depends(get_db), user: User = Depends(require("AICTE_ADMIN"))):
    """DEMO ONLY: remove everything submitted through the portal so the walkthrough can be repeated.

    The audit trail is append-only, so it is kept and the reset itself is recorded in it.
    """
    if not config.DEMO_MODE:
        raise HTTPException(404)
    from sqlalchemy import delete
    enrol_ids = list(db.scalars(select(Enrolment.id).where(Enrolment.batch_id.is_not(None))))
    student_ids = set(db.scalars(select(Enrolment.student_id).where(Enrolment.id.in_(enrol_ids))))
    db.execute(delete(Credential).where(Credential.enrolment_id.in_(enrol_ids)))
    db.execute(delete(Finding).where(or_(Finding.batch_id.is_not(None), Finding.enrolment_id.in_(enrol_ids))))
    db.execute(delete(Enrolment).where(Enrolment.id.in_(enrol_ids)))
    still_enrolled = set(db.scalars(select(Enrolment.student_id).where(Enrolment.student_id.in_(student_ids))))
    orphans = list(student_ids - still_enrolled)
    db.execute(delete(VerificationLog).where(VerificationLog.student_id.in_(orphans)))
    db.execute(delete(ConsentRequest).where(ConsentRequest.student_id.in_(orphans)))
    db.execute(delete(Credential).where(Credential.student_id.in_(orphans)))
    db.execute(delete(Student).where(Student.id.in_(orphans)))
    batches = db.execute(delete(UploadBatch)).rowcount
    result = run_scan(db)
    score_institutions(db)
    audit.record(db, user.username, user.role, "DEMO_RESET", "dataset", "national",
                 {"removed_enrolments": len(enrol_ids), "removed_batches": batches})
    db.commit()
    events.publish("scan", result)
    return {"removed_enrolments": len(enrol_ids), "removed_students": len(orphans), "removed_batches": batches}


# --------------------------------------------------------------------------- reports
@app.get("/api/reports/excess-intake.csv")
def report_excess(db: Session = Depends(get_db), token: str = ""):
    _require_token(token, AICTE)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["AICTE PID", "Institution", "State", "Programme", "Approved intake", "Within-intake admitted",
                "Excess"])
    for inst in db.scalars(select(Institution).order_by(Institution.state)):
        for p in services.programme_ledger(db, inst.id):
            if p["excess"] > 0:
                w.writerow([_cell(x) for x in (inst.aicte_pid, inst.name, inst.state, p["name"],
                                                p["approved_intake"], p["within_intake"], p["excess"])])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=excess_intake_report.csv"})


@app.get("/api/reports/state-summary.xlsx")
def report_states(db: Session = Depends(get_db), token: str = ""):
    _require_token(token, AICTE)
    d = services.national_dashboard(db)
    wb = Workbook()
    ws = wb.active
    ws.title = "State summary"
    ws.append(["State", "Institutions", "Approved intake", "Enrolled (within intake)", "Utilisation",
               "Excess admissions", "High-risk institutions", "Average risk"])
    for s in d["states"]:
        ws.append([_cell(s["state"]), s["institutions"], s["intake"], s["enrolled"], s["utilisation"], s["excess"],
                   s["high_risk"], s["avg_risk"]])
    ws2 = wb.create_sheet("Findings by rule")
    ws2.append(["Rule", "Title", "Severity", "Open findings"])
    for code, n in sorted(d["findings_by_rule"].items()):
        ws2.append([code, RULES[code][1], RULES[code][0], n])
    ws3 = wb.create_sheet("Diversity")
    ws3.append(["Dimension", "Value", "Students"])
    for dim in ("gender", "category", "level"):
        for k, v in d[dim].items():
            ws3.append([dim, k, v])
    buf = io.BytesIO()
    wb.save(buf)
    return Response(buf.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": "attachment; filename=state_summary.xlsx"})


def _cell(v):
    """Neutralise spreadsheet formulas in exported text (CSV / Excel injection)."""
    return "'" + v if isinstance(v, str) and v[:1] in ("=", "+", "-", "@") else v


def _require_token(token: str, roles) -> User:
    if not token:
        raise HTTPException(401, "Login required")
    user = parse_token(token)
    if user.role not in roles:
        raise HTTPException(403, "Not allowed")
    return user


def _404(what: str):
    raise HTTPException(404, f"{what} not found")


# --------------------------------------------------------------------------- frontend
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        # Resolve and confine to the build folder so "../" cannot reach the data directory.
        f = (DIST / path).resolve()
        if path and f.is_file() and f.is_relative_to(DIST.resolve()):
            return FileResponse(f)
        return HTMLResponse((DIST / "index.html").read_text())
