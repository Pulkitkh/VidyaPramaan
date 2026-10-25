"""Vidya Pramaan API: APAAR-linked student data, validation, monitoring and verification."""
import csv
import hashlib
import hmac
import io
import logging
import secrets
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import BackgroundTasks, Body, Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from openpyxl import Workbook
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from . import audit, config, events, services
from .apaar_registry import is_valid_format, mask
from .auth import User, current_user, issue_ticket, issue_token, otp_hash, parse_ticket, require
from .certificates import qr_png, render_certificate, verify_url
from .credentials import ISSUER_DID, build_credential, did_document, key_id, public_jwk, sign_compact, verify_compact, verify_vc
from .db import Base, SessionLocal, engine, get_db
from .keys import ensure_current_key
from .models import (ApiKey, AuditCheckpoint, AuditEvent, ConsentRequest, Credential, Enrolment, Finding,
                     Institution, Programme, Setting, Student, UploadBatch, VerificationLog, now)
from .validation import COLUMNS, ENUMS, MAX_ROWS, RULES, parse_csv, parse_xlsx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("vidyapramaan")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        rotated = ensure_current_key(db)
        if rotated:
            log.info("issuer key changed; re-signed %s credentials and %s checkpoints",
                     rotated["credentials_resigned"], rotated["checkpoints_resigned"])
    yield


app = FastAPI(title="Vidya Pramaan API", version="0.2.0", lifespan=lifespan,
              description="APAAR ID-based student data management and verification (SIH26263 prototype). "
                          "All data is synthetic.")


@app.exception_handler(audit.AuditUnavailable)
def _audit_busy(request: Request, exc: audit.AuditUnavailable):
    return JSONResponse({"detail": str(exc)}, status_code=503, headers={"Retry-After": "5"})

AICTE = ("AICTE_ADMIN", "AUDITOR")                 # national roles that may see student-level records
MONITOR = AICTE + ("REGULATOR",)                    # roles that see aggregated monitoring
CAN_ISSUE = ("AICTE_ADMIN", "INSTITUTION_ADMIN", "STUDENT", "UNIVERSITY")  # may create a credential on demand
SCOPE_FIELDS = {"enrolment_status", "programme", "institution", "admission_year", "name", "year_of_study"}
CONSENT_WINDOW = timedelta(hours=24)
OTP_ATTEMPTS = 5


# --------------------------------------------------------------------------- security middleware
CSP = ("default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
       "connect-src 'self'; font-src 'self' data:; worker-src 'self'; manifest-src 'self'; object-src 'none'; "
       "base-uri 'self'; frame-ancestors 'none'; form-action 'self'")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    h = resp.headers
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("Referrer-Policy", "no-referrer")
    h.setdefault("X-Frame-Options", "DENY")
    h.setdefault("Permissions-Policy", "camera=(self), microphone=(), geolocation=()")
    if not request.url.path.startswith(("/docs", "/redoc")):  # Swagger UI loads its own assets
        h.setdefault("Content-Security-Policy", CSP)
    if request.url.scheme == "https":
        h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if request.url.path.startswith("/api/"):
        h.setdefault("Cache-Control", "no-store")
    return resp


class RateLimiter:
    """Sliding-window limits per client address, in memory (one process). Production: API gateway."""

    def __init__(self):
        self.hits: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def check(self, request: Request, bucket: str, limit: int, window: int = 60) -> None:
        key = f"{bucket}:{request.client.host if request.client else '-'}"
        t = time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and q[0] < t - window:
                q.popleft()
            if len(q) >= limit:
                raise HTTPException(429, "Too many requests, please wait a minute")
            q.append(t)


limiter = RateLimiter()


# --------------------------------------------------------------------------- auth
def demo_users(db: Session) -> list[User]:
    persona = db.get(Setting, "persona_student_id")
    student = db.get(Student, int(persona.value)) if persona else None
    demo_inst = db.get(Institution, 1)
    uni = demo_inst.university if demo_inst else None
    return [
        User("aicte.admin", "AICTE_ADMIN", "AICTE Regulation Bureau (officer)"),
        User("inst.admin", "INSTITUTION_ADMIN", "Demo Institute of Technology, Pune", institution_id=1),
        User("university.registrar", "UNIVERSITY", f"Registrar, {uni}" if uni else "Affiliating university",
             university=uni, org=uni),
        User("dte.regulator", "REGULATOR", "Directorate of Technical Education, Maharashtra (demo)",
             org="DTE Maharashtra (demo)", state="Maharashtra"),
        User("hr.verifier", "VERIFIER", "Acme Technologies (employer)",
             org="Acme Technologies Pvt Ltd (demo employer)"),
        User("student.ananya", "STUDENT", "Ananya Kulkarni (student)", student_id=student.id if student else None),
        User("auditor", "AUDITOR", "Internal auditor (read-only)"),
    ]


def _demo_only():
    if not config.DEMO_MODE:
        raise HTTPException(404, "Not available")


@app.get("/api/auth/demo-users")
def list_demo_users(db: Session = Depends(get_db)):
    _demo_only()
    return [u.__dict__ for u in demo_users(db)]


@app.post("/api/auth/demo-login")
def demo_login(request: Request, username: str = Body(embed=True), db: Session = Depends(get_db)):
    """Demo only: one-click sign-in per role. Production uses AICTE SSO (OIDC + MFA)."""
    _demo_only()
    limiter.check(request, "login", 30)
    user = next((u for u in demo_users(db) if u.username == username), None)
    if not user:
        raise HTTPException(404, "Unknown demo user")
    audit.record(db, user.username, user.role, "LOGIN", "session", user.username)
    db.commit()
    return {"token": issue_token(user), "user": user.__dict__}


@app.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    return user.__dict__


# --------------------------------------------------------------------------- meta & rules
@app.get("/api/meta")
def meta():
    return {"rules": {k: {"severity": v[0], "title": v[1]} for k, v in RULES.items()},
            "ruleset_version": config.RULESET_VERSION, "academic_year": config.CURRENT_ACADEMIC_YEAR,
            "supernumerary": {k: v["caps"] for k, v in config.SUPERNUMERARY.items()},
            "admission_window": config.ADMISSION_WINDOW, "apaar_registry": config.APAAR_REGISTRY,
            "columns": COLUMNS, "demo_mode": config.DEMO_MODE, "demo_pin_required": bool(config.DEMO_PIN),
            "issuer_key_id": key_id()}


@app.get("/api/rules")
def rules():
    """The full regulatory ruleset in force, with each value's source and whether it was verified."""
    return {"ruleset": config.RULESET, "rules": [{"code": k, "severity": v[0], "title": v[1]} for k, v in RULES.items()]}


@app.post("/api/events/ticket")
def event_ticket(user: User = Depends(current_user)):
    """A 60-second ticket for the live event stream, so the session token never goes into a URL."""
    return {"ticket": issue_ticket(user, "events")}


@app.get("/api/events")
async def sse(ticket: str):
    user = parse_ticket(ticket, "events")
    return StreamingResponse(events.stream(user), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# --------------------------------------------------------------------------- AICTE / regulator monitoring
@app.get("/api/dashboard/national")
def dashboard(db: Session = Depends(get_db), _: User = Depends(require(*MONITOR))):
    return services.national_dashboard(db)


def _state_scope(user: User) -> str | None:
    return user.state if user.role == "REGULATOR" else None


@app.get("/api/institutions")
def institutions(q: str = "", state: str = "", sort: str = "risk", limit: int = Query(50, ge=1, le=200),
                 offset: int = Query(0, ge=0), db: Session = Depends(get_db), user: User = Depends(require(*MONITOR))):
    stmt = select(Institution)
    state = _state_scope(user) or state
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
    return {"total": total, "scope": state or "national", "items": [
        {"id": i.id, "name": i.name, "aicte_pid": i.aicte_pid, "state": i.state, "city": i.city,
         "region": i.region, "type": i.inst_type, "university": i.university, "risk_score": i.risk_score,
         "quality_score": i.quality_score, "reasons": i.risk_reasons, "intake": intake.get(i.id, 0),
         "enrolled": enrolled.get(i.id, 0), "open_findings": open_f.get(i.id, 0)} for i in rows]}


@app.get("/api/institutions/{inst_id}")
def institution_detail(inst_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    inst = db.get(Institution, inst_id) or _404("Institution")
    allowed = (user.role in AICTE or user.institution_id == inst_id
               or (user.role == "REGULATOR" and inst.state == user.state)
               or (user.role == "UNIVERSITY" and inst.university == user.university))
    if not allowed:
        raise HTTPException(403, "Not your institution")
    by_rule = dict(db.execute(select(Finding.rule_code, func.count())
                              .where(Finding.institution_id == inst_id, Finding.status == "OPEN")
                              .group_by(Finding.rule_code)).all())
    batches = db.scalars(select(UploadBatch).where(UploadBatch.institution_id == inst_id)
                         .order_by(UploadBatch.id.desc()).limit(10)).all()
    return {"id": inst.id, "name": inst.name, "aicte_pid": inst.aicte_pid, "state": inst.state,
            "city": inst.city, "region": inst.region, "type": inst.inst_type, "university": inst.university,
            "risk_score": inst.risk_score, "quality_score": inst.quality_score, "reasons": inst.risk_reasons,
            "ledger": services.programme_ledger(db, inst_id), "findings_by_rule": by_rule,
            "batches": [_batch_summary(b) for b in batches]}


@app.get("/api/findings")
def findings(institution_id: int | None = None, rule: str = "", severity: str = "", status: str = "OPEN",
             limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db: Session = Depends(get_db),
             user: User = Depends(current_user)):
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
        if e is not None:
            out["record"] = {"student": services.student_public(e.student), "enrolment": services.enrolment_dict(e)}
            other = _counterpart(db, e, f)
            if other:
                out["counterpart"] = {"student": services.student_public(other.student),
                                      "enrolment": services.enrolment_dict(other)}
    if f.rule_code == "DUP-004" and user.role in AICTE:
        out["cluster"] = (f.evidence or {}).get("members", [])
    return out


def _counterpart(db: Session, e: Enrolment, f: Finding) -> Enrolment | None:
    if f.rule_code == "DUP-002" and f.related_institution_id:
        return db.scalars(select(Enrolment).where(Enrolment.institution_id == f.related_institution_id,
                                                  Enrolment.student_id == e.student_id,
                                                  Enrolment.status == "ACTIVE")).first()
    if f.rule_code == "DUP-003":
        other = (f.evidence or {}).get("counterpart_enrolment")
        return db.get(Enrolment, other) if other else None
    return None


class Decision(BaseModel):
    decision: str
    note: str = ""


@app.post("/api/findings/{fid}/decision")
def decide(fid: int, body: Decision, db: Session = Depends(get_db), user: User = Depends(require("AICTE_ADMIN"))):
    f = db.get(Finding, fid) or _404("Finding")
    if body.decision not in ("RESOLVED", "DISMISSED", "ESCALATED"):
        raise HTTPException(400, "decision must be RESOLVED, DISMISSED or ESCALATED")
    if len(body.note.strip()) < 5:
        raise HTTPException(400, "Write a short reason (at least 5 characters); it goes into the audit trail")
    f.status, f.resolution_note, f.decided_by, f.decided_at = body.decision, body.note.strip(), user.username, now()
    audit.record(db, user.username, user.role, f"FINDING_{body.decision}", "finding", f.id,
                 {"rule": f.rule_code, "institution_id": f.institution_id, "note": f.resolution_note,
                  "fingerprint": f.fingerprint})
    db.commit()
    return services.finding_dict(f)


@app.post("/api/scan")
def scan(db: Session = Depends(get_db), user: User = Depends(require("AICTE_ADMIN"))):
    result = services.refresh_national(db, user.username, user.role)
    db.commit()
    events.publish("scan", result)
    return result


@app.get("/api/aicte/students/{apaar_id}")
def statutory_lookup(apaar_id: str, purpose: str = Query(min_length=10), db: Session = Depends(get_db),
                     user: User = Depends(require("AICTE_ADMIN"))):
    """Regulatory lookup without student consent (legitimate use for a statutory function); always logged
    and shown to the student in their access log."""
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
            "error_rows": b.error_rows, "warning_rows": b.warning_rows, "committed_rows": b.committed_rows,
            "column_map": b.column_map or {}}


@app.get("/api/institution/overview")
def inst_overview(db: Session = Depends(get_db), user: User = Depends(require("INSTITUTION_ADMIN"))):
    return institution_detail(_my_inst(db, user).id, db, user)


TEMPLATE_EXAMPLE = {"apaar_id": "123456789012", "apaar_consent": "GIVEN", "roll_no": "0001BTCSE26001",
                    "name": "Student Name", "dob": "2008-01-31", "gender": "F", "category": "GEN",
                    "father_name": "Father Name", "mother_name": "Mother Name", "guardian_name": "",
                    "programme_code": "BTCSE", "admission_year": 2026, "year_of_study": 1,
                    "admission_type": "REGULAR", "quota": "STATE_CAP", "nationality": "Indian", "fn_status": "N",
                    "oci_status": "N", "oci_card_no": "", "passport_no": "", "nri_status": "N", "nri_country": "",
                    "pwd": "N", "admission_date": "2026-08-01", "mobile": "9800000000", "email": "student@example.in"}  # nosec B105


@app.get("/api/institution/template.csv")
def template():
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS)
    w.writeheader()
    w.writerow(TEMPLATE_EXAMPLE)
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
    ws.append([TEMPLATE_EXAMPLE[c] for c in COLUMNS])
    yes_no = {"fn_status", "oci_status", "nri_status", "pwd"}
    for idx, col in enumerate(COLUMNS, start=1):
        letter = ws.cell(row=1, column=idx).column_letter
        ws.column_dimensions[letter].width = max(12, len(col) + 2)
        choices = sorted(ENUMS[col]) if col in ENUMS else ["Y", "N"] if col in yes_no else None
        if choices:
            dv = DataValidation(type="list", formula1='"' + ",".join(choices) + '"', allow_blank=True)
            ws.add_data_validation(dv)
            dv.add(f"{letter}2:{letter}5000")
        if col in ("apaar_id", "roll_no", "dob", "admission_date", "mobile"):
            for r in range(2, 5001):
                ws.cell(row=r, column=idx).number_format = "@"  # keep IDs and dates as text
    ws.freeze_panes = "A2"
    guide = wb.create_sheet("How to fill")
    guide.append(["Column", "Required", "Notes"])
    notes = {"apaar_consent": "GIVEN or REFUSED. Never left blank: consent is not assumed.",
             "father_name": "Give at least one of father, mother or guardian.",
             "admission_year": "Year of admission; continuing students keep their original year.",
             "mobile": "Optional. 10-digit Indian mobile. Used to detect shared-contact clusters.",
             "apaar_id": "12 digits. Leave blank for FN/OCI students or students who declined APAAR."}
    for c in COLUMNS:
        guide.append([c, "yes" if c in services_required() else "", notes.get(c, "")])
    buf = io.BytesIO()
    wb.save(buf)
    return Response(buf.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": "attachment; filename=student_upload_template.xlsx"})


def services_required() -> set[str]:
    from .validation import REQUIRED
    return set(REQUIRED)


@app.get("/api/institution/sample.csv")
def sample_csv():
    return FileResponse(config.SAMPLE_CSV, media_type="text/csv", filename=config.SAMPLE_CSV.name)


MAX_UPLOAD_BYTES = 10_000_000


@app.post("/api/institution/uploads")
async def upload(file: UploadFile = File(...), db: Session = Depends(get_db),
                 user: User = Depends(require("INSTITUTION_ADMIN"))):
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 10 MB. Split it, or send rows through the integration API.")
    name = (file.filename or "").lower()
    try:
        rows = parse_xlsx(content) if name.endswith((".xlsx", ".xlsm")) else parse_csv(content)
    except UnicodeDecodeError:
        raise HTTPException(400, "CSV files must be UTF-8. Excel users can upload the .xlsx directly.")
    except Exception:
        raise HTTPException(400, "Could not read the file. Use the CSV or Excel template.")
    if not rows:
        raise HTTPException(400, "No rows found")
    if len(rows) > MAX_ROWS:
        raise HTTPException(413, f"At most {MAX_ROWS} rows per upload; split the file by programme.")
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


_scan_lock = threading.Lock()


def refresh_in_background() -> None:
    """National scan + risk refresh after a write, off the request path. One scan runs at a time."""
    with _scan_lock, SessionLocal() as db:
        result = services.refresh_national(db)
        db.commit()
    events.publish("scan", result)


def _publish_commit(db: Session, b: UploadBatch, result: dict) -> None:
    inst = db.get(Institution, b.institution_id)
    events.publish("batch_committed", {"institution": inst.name, "institution_id": inst.id, "source": b.source,
                                       **{k: result[k] for k in ("created", "updated", "rejected")},
                                       "risk_score": inst.risk_score}, institution_id=inst.id)


@app.post("/api/institution/uploads/{bid}/commit")
def commit(bid: int, tasks: BackgroundTasks, db: Session = Depends(get_db),
           user: User = Depends(require("INSTITUTION_ADMIN"))):
    b = db.get(UploadBatch, bid) or _404("Batch")
    if b.institution_id != user.institution_id:
        raise HTTPException(403, "Not your batch")
    if b.status != "VALIDATED":
        raise HTTPException(409, f"Batch already {b.status}")
    result = services.commit_batch(db, b, user, scan=False)
    db.commit()
    _publish_commit(db, b, result)
    tasks.add_task(refresh_in_background)
    return {**_batch_summary(b), **result}


@app.get("/api/institution/students")
def inst_students(q: str = "", status: str = "", limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db),
                  user: User = Depends(require("INSTITUTION_ADMIN"))):
    stmt = select(Enrolment).join(Student).where(Enrolment.institution_id == user.institution_id)
    if q:
        stmt = stmt.where(or_(Student.name.ilike(f"%{q}%"), Enrolment.roll_no.ilike(f"%{q}%"),
                              Student.apaar_id.ilike(f"%{q}%")))
    if status:
        stmt = stmt.where(Enrolment.status == status)
    rows = db.scalars(stmt.order_by(Enrolment.id.desc()).limit(limit)).all()
    return [{"student": services.student_public(e.student, reveal=True), "enrolment": services.enrolment_dict(e)}
            for e in rows]


class ExitIn(BaseModel):
    status: str
    date: date
    reason: str = Field(min_length=5, max_length=300)


@app.post("/api/institution/enrolments/{eid}/exit")
def record_exit(eid: int, body: ExitIn, tasks: BackgroundTasks, db: Session = Depends(get_db),
                user: User = Depends(require("INSTITUTION_ADMIN"))):
    """Withdrawal, transfer out, graduation or drop-out. The record stays; its status and credential change."""
    e = db.get(Enrolment, eid) or _404("Enrolment")
    if e.institution_id != user.institution_id:
        raise HTTPException(403, "Not your student")
    if body.date > date.today() or body.date < e.admission_date:
        raise HTTPException(400, "Exit date must be between the admission date and today")
    try:
        result = services.exit_enrolment(db, e, body.status, body.date, body.reason, user)
    except ValueError as ex:
        raise HTTPException(400, str(ex))
    db.commit()
    events.publish("enrolment_exit", {"institution_id": e.institution_id, "status": body.status},
                   institution_id=e.institution_id)
    tasks.add_task(refresh_in_background)
    return result


# --------------------------------------------------------------------------- per-institution API keys
def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


@app.get("/api/institution/api-keys")
def list_keys(db: Session = Depends(get_db), user: User = Depends(require("INSTITUTION_ADMIN"))):
    rows = db.scalars(select(ApiKey).where(ApiKey.institution_id == user.institution_id).order_by(ApiKey.id.desc()))
    return [{"id": k.id, "label": k.label, "prefix": k.prefix, "created_at": k.created_at,
             "last_used_at": k.last_used_at, "revoked": k.revoked} for k in rows]


@app.post("/api/institution/api-keys")
def create_key(label: str = Body(embed=True, min_length=3, max_length=80), db: Session = Depends(get_db),
               user: User = Depends(require("INSTITUTION_ADMIN"))):
    raw = "vpk_" + secrets.token_urlsafe(32)
    k = ApiKey(institution_id=user.institution_id, label=label, prefix=raw[:12], key_hash=_hash_key(raw),
               created_by=user.username)
    db.add(k)
    db.flush()
    audit.record(db, user.username, user.role, "API_KEY_CREATED", "api_key", k.id, {"label": label, "prefix": k.prefix})
    db.commit()
    return {"id": k.id, "label": label, "prefix": k.prefix, "key": raw,
            "note": "Shown once. Store it in your ERP's secret store; only a hash is kept here."}


@app.delete("/api/institution/api-keys/{kid}")
def revoke_key(kid: int, db: Session = Depends(get_db), user: User = Depends(require("INSTITUTION_ADMIN"))):
    k = db.get(ApiKey, kid) or _404("API key")
    if k.institution_id != user.institution_id:
        raise HTTPException(403, "Not your key")
    k.revoked = True
    audit.record(db, user.username, user.role, "API_KEY_REVOKED", "api_key", k.id, {"prefix": k.prefix})
    db.commit()
    return {"id": k.id, "revoked": True}


def integration_user(authorization: str | None = Header(default=None), x_api_key: str | None = Header(default=None),
                     db: Session = Depends(get_db)) -> User:
    """ERP systems authenticate with an institution API key; a signed-in institution admin may also call."""
    if x_api_key:
        k = db.scalars(select(ApiKey).where(ApiKey.key_hash == _hash_key(x_api_key))).first()
        if k is None or k.revoked:
            raise HTTPException(401, "Invalid or revoked API key")
        k.last_used_at = now()
        db.commit()
        return User(f"apikey:{k.prefix}", "INSTITUTION_ADMIN", k.label, institution_id=k.institution_id)
    user = current_user(authorization)
    if user.role != "INSTITUTION_ADMIN":
        raise HTTPException(403, "Institution credentials required")
    return user


# --------------------------------------------------------------------------- ERP / system integration API
@app.post("/api/v1/students:validate", tags=["integration"])
def api_validate(rows: list[dict] = Body(...), db: Session = Depends(get_db), user: User = Depends(integration_user)):
    """Dry-run validation for institutional ERPs; nothing is stored."""
    from .validation import map_columns, validate_rows
    if len(rows) > MAX_ROWS:
        raise HTTPException(413, f"At most {MAX_ROWS} rows per call")
    mapped, _, _ = map_columns(rows)
    return validate_rows(db, _my_inst(db, user), mapped)


@app.post("/api/v1/students:submit", tags=["integration"])
def api_submit(tasks: BackgroundTasks, rows: list[dict] = Body(...), commit_now: bool = True,
               idempotency_key: str | None = Header(default=None, max_length=80), db: Session = Depends(get_db),
               user: User = Depends(integration_user)):
    """Validate and (optionally) commit a JSON batch in one call. Send an Idempotency-Key header to make
    retries safe: the same key returns the original result instead of submitting twice."""
    if len(rows) > MAX_ROWS:
        raise HTTPException(413, f"At most {MAX_ROWS} rows per call")
    if idempotency_key:
        prior = db.scalars(select(UploadBatch).where(UploadBatch.institution_id == user.institution_id,
                                                     UploadBatch.idempotency_key == idempotency_key)).first()
        if prior:
            return {**_batch_summary(prior), "replayed": True, "rows": prior.row_results}
    batch = services.create_batch(db, _my_inst(db, user), rows, "api-submission", user, source="API",
                                  idempotency_key=idempotency_key)
    result = services.commit_batch(db, batch, user, scan=False) if commit_now else {}
    db.commit()
    if result:
        _publish_commit(db, batch, result)
        tasks.add_task(refresh_in_background)
    return {**_batch_summary(batch), **result, "rows": batch.row_results}


@app.get("/api/v1/certificate-data/{enrolment_id}", tags=["integration"])
def certificate_data(enrolment_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Fields a degree-awarding body needs to print APAAR ID + student ID + verification QR."""
    e = _authorised_enrolment(db, enrolment_id, user)
    cred = _ensure_credential(db, e, user)
    db.commit()
    return {"apaar_id": e.student.apaar_id, "provisional_id": e.student.provisional_id, "student_id": e.roll_no,
            "name": e.student.name, "programme": e.programme.name, "institution": e.institution.name,
            "university": e.institution.university, "qr_payload": verify_url(cred.token), "credential_id": cred.id}


# --------------------------------------------------------------------------- credentials & certificates
def _authorised_enrolment(db: Session, enrolment_id: int, user: User) -> Enrolment:
    e = db.get(Enrolment, enrolment_id) or _404("Enrolment")
    ok = (user.role in AICTE or (user.role == "INSTITUTION_ADMIN" and e.institution_id == user.institution_id)
          or (user.role == "STUDENT" and e.student_id == user.student_id)
          or (user.role == "UNIVERSITY" and e.institution.university == user.university))
    if not ok:
        raise HTTPException(403, "Not allowed")
    return e


def _ensure_credential(db: Session, e: Enrolment, user: User) -> Credential:
    cred = db.scalars(select(Credential).where(Credential.enrolment_id == e.id, Credential.status == "ACTIVE")).first()
    if cred:
        return cred
    if user.role not in CAN_ISSUE:
        raise HTTPException(404, "No credential has been issued for this enrolment yet (read-only role)")
    if e.status != "ACTIVE":
        raise HTTPException(409, f"Enrolment is {e.status}; no new enrolment credential can be issued")
    cred_id, vc, token = build_credential(e.student, e)
    cred = Credential(id=cred_id, student_id=e.student_id, enrolment_id=e.id, vc=vc, token=token)
    db.add(cred)
    audit.record(db, user.username, user.role, "CREDENTIAL_ISSUED", "credential", cred_id, {"enrolment": e.id})
    return cred


@app.get("/api/enrolments/{enrolment_id}/certificate.pdf")
def certificate(enrolment_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
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
    return {"id": cred.id, "status": cred.status, "reason": cred.status_reason, "enrolment_status": e.status,
            "checked_at": now()}


@app.get("/api/issuer/jwk")
def issuer_key():
    return {**public_jwk(), "key_id": key_id()}


@app.get("/.well-known/did.json")
def did_json():
    return JSONResponse(did_document(), media_type="application/did+json")


STATUS_LIST_TTL = timedelta(hours=24)


@app.get("/api/credentials/status-list")
def credential_status_list(request: Request, db: Session = Depends(get_db)):
    """Public, signed list of every credential that is no longer valid. A verifier caches it while online;
    an offline check then reports revocation status "as of" the list time, not just a valid signature."""
    limiter.check(request, "status-list", 30)
    rows = db.execute(select(Credential.id, Credential.status).where(Credential.status != "ACTIVE")).all()
    issued = now()
    claims = {"typ": "revocation-list", "iss": ISSUER_DID, "iat": issued.isoformat(timespec="seconds"),
              "exp": (issued + STATUS_LIST_TTL).isoformat(timespec="seconds"),
              "revoked": sorted(i for i, st in rows if st == "REVOKED"),
              "superseded": sorted(i for i, st in rows if st == "SUPERSEDED")}
    return {"token": sign_compact(claims), "count": len(rows), "issued_at": claims["iat"], "expires_at": claims["exp"]}


@app.post("/api/verify/token")
def verify_token(request: Request, token: str = Body(embed=True, max_length=4000), db: Session = Depends(get_db)):
    """Public: verify a QR token. Signature is checked offline; status is checked live."""
    limiter.check(request, "verify", 60)
    valid, claims = verify_compact(token)
    out = {"signature_valid": valid, "claims": claims, "issuer": public_jwk()["kid"]}
    if valid and claims:
        cred = db.get(Credential, claims.get("cid"))
        out["registry_status"] = cred.status if cred else "UNKNOWN"
        if cred:
            e = db.get(Enrolment, cred.enrolment_id)
            out["enrolment_status_now"] = e.status
            out["status_reason"] = cred.status_reason
            # Log a public scan in the student's access history, at most once per credential per 10 minutes,
            # so repeated scans (or someone scripting them) cannot flood it.
            recent = db.scalar(select(func.count()).select_from(VerificationLog).where(
                VerificationLog.student_id == cred.student_id, VerificationLog.basis == "CREDENTIAL",
                VerificationLog.created_at >= now() - timedelta(minutes=10)))
            if not recent:
                db.add(VerificationLog(student_id=cred.student_id, verifier_org="Public QR verification",
                                       basis="CREDENTIAL", purpose="QR scan", disclosed=claims))
                db.commit()
    status = out.get("registry_status")
    out["verdict"] = ("VERIFIED" if valid and status == "ACTIVE" else "SUPERSEDED" if valid and status == "SUPERSEDED"
                      else "REVOKED" if valid and status == "REVOKED" else "UNKNOWN" if valid
                      else "TAMPERED_OR_INVALID")
    return out


@app.post("/api/verify/vc")
def verify_full_vc(vc: dict = Body(...)):
    return {"signature_valid": verify_vc(vc), "id": vc.get("id"), "issuer": (vc.get("issuer") or {}).get("id")}


# --------------------------------------------------------------------------- consent-based verification
class ConsentIn(BaseModel):
    apaar_id: str
    purpose: str = Field(min_length=10, max_length=200)
    scope: list[str]


@app.post("/api/verify/consent-requests")
def request_consent(request: Request, body: ConsentIn, db: Session = Depends(get_db),
                    user: User = Depends(require("VERIFIER"))):
    limiter.check(request, "consent", 20)
    if not is_valid_format(body.apaar_id):
        raise HTTPException(400, "APAAR ID must be 12 digits")
    bad = set(body.scope) - SCOPE_FIELDS
    if bad or not body.scope:
        raise HTTPException(400, f"Scope must be a subset of {sorted(SCOPE_FIELDS)}")
    s = db.scalars(select(Student).where(Student.apaar_id == body.apaar_id)).first()
    # The reply is the same whether or not the APAAR ID exists, so requests cannot be used to probe the registry.
    otp = f"{secrets.randbelow(10**6):06d}"
    c = ConsentRequest(student_id=s.id if s else None, apaar_masked=mask(body.apaar_id),
                       verifier_org=user.org or user.display_name, verifier_user=user.username,
                       purpose=body.purpose.strip(), scope=body.scope, otp_hash="",
                       demo_otp=otp if config.DEMO_MODE else None, expires_at=now() + CONSENT_WINDOW)
    db.add(c)
    db.flush()
    c.otp_hash = otp_hash(c.id, otp)
    audit.record(db, user.username, user.role, "CONSENT_REQUESTED", "consent", c.id,
                 {"apaar": mask(body.apaar_id), "purpose": c.purpose, "scope": body.scope})
    db.commit()
    if s:
        events.publish("consent_requested", {"consent_id": c.id}, roles=set(), student_id=s.id)
        log.info("consent request %s sent to student (OTP delivered via registered mobile in production)", c.id)
    return _consent_dict(c, show_otp=False)


@app.get("/api/verify/consent-requests")
def my_requests(db: Session = Depends(get_db), user: User = Depends(require("VERIFIER"))):
    rows = db.scalars(select(ConsentRequest).where(ConsentRequest.verifier_user == user.username)
                      .order_by(ConsentRequest.id.desc()).limit(100)).all()
    return [_consent_dict(_expire(db, c), show_otp=False) for c in rows]


def _expire(db: Session, c: ConsentRequest) -> ConsentRequest:
    if c.status in ("PENDING", "APPROVED") and c.expires_at < now():
        c.status = "EXPIRED"
        db.commit()
    return c


@app.get("/api/verify/consent-requests/{cid}/result")
def consent_result(cid: int, db: Session = Depends(get_db), user: User = Depends(require("VERIFIER"))):
    c = db.get(ConsentRequest, cid) or _404("Consent")
    if c.verifier_user != user.username:
        raise HTTPException(403, "Not your request")
    _expire(db, c)
    if c.status != "APPROVED":
        return {"status": c.status, "disclosed": None}
    e = db.scalars(select(Enrolment).where(Enrolment.student_id == c.student_id)
                   .order_by((Enrolment.status == "ACTIVE").desc(), Enrolment.id.desc())).first()
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
         "apaar": c.apaar_masked, "created_at": c.created_at, "expires_at": c.expires_at, "decided_at": c.decided_at,
         "attempts_left": max(0, OTP_ATTEMPTS - (c.attempts or 0))}
    if show_otp and c.demo_otp:
        d["demo_otp"] = c.demo_otp  # demo only: in production the OTP goes to the student's registered mobile
    return d


# --------------------------------------------------------------------------- student self-service
@app.get("/api/me/record")
def my_record(db: Session = Depends(get_db), user: User = Depends(require("STUDENT"))):
    s = db.get(Student, user.student_id) or _404("Student")
    enrols = db.scalars(select(Enrolment).where(Enrolment.student_id == s.id)).all()
    creds = db.scalars(select(Credential).where(Credential.student_id == s.id)).all()
    logs = db.scalars(select(VerificationLog).where(VerificationLog.student_id == s.id)
                      .order_by(VerificationLog.id.desc()).limit(100)).all()
    return {"student": services.student_public(s, reveal=True),
            "enrolments": [services.enrolment_dict(e) for e in enrols],
            "credentials": [{"id": c.id, "status": c.status, "reason": c.status_reason, "issued_at": c.issued_at,
                             "enrolment_id": c.enrolment_id, "vc": c.vc, "token": c.token,
                             "verify_url": verify_url(c.token)} for c in creds],
            "access_log": [{"id": l.id, "verifier_org": l.verifier_org, "basis": l.basis, "purpose": l.purpose,
                            "disclosed": l.disclosed, "at": l.created_at} for l in logs]}


@app.get("/api/me/consents")
def my_consents(db: Session = Depends(get_db), user: User = Depends(require("STUDENT"))):
    rows = db.scalars(select(ConsentRequest).where(ConsentRequest.student_id == user.student_id)
                      .order_by(ConsentRequest.id.desc())).all()
    return [_consent_dict(_expire(db, c), show_otp=config.DEMO_MODE and c.status == "PENDING") for c in rows]


class ConsentDecision(BaseModel):
    decision: str
    otp: str = ""


@app.post("/api/me/consents/{cid}/decision")
def decide_consent(cid: int, body: ConsentDecision, db: Session = Depends(get_db),
                   user: User = Depends(require("STUDENT"))):
    c = db.get(ConsentRequest, cid) or _404("Consent")
    if c.student_id != user.student_id:
        raise HTTPException(403, "Not your consent request")
    _expire(db, c)
    if c.status != "PENDING":
        raise HTTPException(409, f"Already {c.status}")
    if body.decision == "APPROVE":
        if not hmac.compare_digest(otp_hash(c.id, body.otp.strip()), c.otp_hash):
            c.attempts = (c.attempts or 0) + 1
            if c.attempts >= OTP_ATTEMPTS:
                c.status = "LOCKED"
                audit.record(db, user.username, user.role, "CONSENT_LOCKED", "consent", c.id, {"attempts": c.attempts})
            db.commit()
            left = max(0, OTP_ATTEMPTS - c.attempts)
            raise HTTPException(400, f"Incorrect OTP. {left} attempt{'s' * (left != 1)} left." if left
                                else "Too many wrong OTPs; this request is locked. Ask the verifier to send a new one.")
        c.status = "APPROVED"
        c.expires_at = now() + CONSENT_WINDOW  # the access window starts when the student approves
    elif body.decision == "DENY":
        c.status = "DENIED"
    else:
        raise HTTPException(400, "decision must be APPROVE or DENY")
    c.decided_at = now()
    c.demo_otp = None
    audit.record(db, user.username, user.role, f"CONSENT_{c.status}", "consent", c.id,
                 {"verifier": c.verifier_org, "scope": c.scope})
    db.commit()
    events.publish("consent_decided", {"consent_id": c.id, "status": c.status}, roles=set(),
                   username=c.verifier_user, student_id=c.student_id)
    return _consent_dict(c, show_otp=False)


@app.post("/api/me/consents/{cid}/revoke")
def revoke_consent(cid: int, db: Session = Depends(get_db), user: User = Depends(require("STUDENT"))):
    c = db.get(ConsentRequest, cid) or _404("Consent")
    if c.student_id != user.student_id:
        raise HTTPException(403, "Not your consent request")
    if c.status != "APPROVED":
        raise HTTPException(409, f"Only an approved consent can be revoked (this one is {c.status})")
    c.status = "REVOKED"
    audit.record(db, user.username, user.role, "CONSENT_REVOKED", "consent", c.id, {})
    db.commit()
    return _consent_dict(c, show_otp=False)


# --------------------------------------------------------------------------- university (degree-awarding body)
def _uni_institutions(db: Session, user: User) -> list[Institution]:
    return db.scalars(select(Institution).where(Institution.university == user.university)
                      .order_by(Institution.name)).all()


@app.get("/api/university/overview")
def university_overview(db: Session = Depends(get_db), user: User = Depends(require("UNIVERSITY"))):
    insts = _uni_institutions(db, user)
    ids = [i.id for i in insts]
    active = dict(db.execute(select(Enrolment.institution_id, func.count()).where(
        Enrolment.institution_id.in_(ids), Enrolment.status == "ACTIVE").group_by(Enrolment.institution_id)).all())
    with_apaar = dict(db.execute(select(Enrolment.institution_id, func.count()).join(Student).where(
        Enrolment.institution_id.in_(ids), Enrolment.status == "ACTIVE", Student.apaar_id.is_not(None))
        .group_by(Enrolment.institution_id)).all())
    creds = dict(db.execute(select(Enrolment.institution_id, func.count()).join(
        Credential, Credential.enrolment_id == Enrolment.id).where(
        Enrolment.institution_id.in_(ids), Credential.status == "ACTIVE").group_by(Enrolment.institution_id)).all())
    return {"university": user.university, "institutions": [
        {"id": i.id, "name": i.name, "aicte_pid": i.aicte_pid, "city": i.city, "active": active.get(i.id, 0),
         "with_apaar": with_apaar.get(i.id, 0), "credentials": creds.get(i.id, 0), "risk_score": i.risk_score}
        for i in insts]}


def _feed_query(db: Session, user: User, institution_id: int | None, q: str):
    ids = [i.id for i in _uni_institutions(db, user)]
    if institution_id:
        if institution_id not in ids:
            raise HTTPException(403, "Institution is not affiliated to your university")
        ids = [institution_id]
    stmt = select(Enrolment).join(Student).where(Enrolment.institution_id.in_(ids), Enrolment.status == "ACTIVE")
    if q:
        stmt = stmt.where(or_(Student.name.ilike(f"%{q}%"), Enrolment.roll_no.ilike(f"%{q}%")))
    return stmt


def _feed_row(e: Enrolment, cred: Credential | None) -> dict:
    return {"enrolment_id": e.id, "name": e.student.name, "apaar_id": e.student.apaar_id,
            "provisional_id": e.student.provisional_id, "student_id": e.roll_no, "programme": e.programme.name,
            "institution": e.institution.name, "aicte_pid": e.institution.aicte_pid, "year_of_study": e.year_of_study,
            "credential_id": cred.id if cred else None, "qr_payload": verify_url(cred.token) if cred else None}


@app.get("/api/university/degree-feed")
def degree_feed(institution_id: int | None = None, q: str = "", limit: int = Query(50, ge=1, le=200),
                offset: int = Query(0, ge=0), db: Session = Depends(get_db), user: User = Depends(require("UNIVERSITY"))):
    """APAAR ID + student ID for printing on certificates (PS requirement 10). Access is audited."""
    stmt = _feed_query(db, user, institution_id, q)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(Enrolment.institution_id, Enrolment.roll_no).limit(limit).offset(offset)).all()
    creds = {c.enrolment_id: c for c in db.scalars(select(Credential).where(
        Credential.enrolment_id.in_([e.id for e in rows]), Credential.status == "ACTIVE"))}
    audit.record(db, user.username, user.role, "DEGREE_FEED_VIEWED", "university", user.university,
                 {"institution_id": institution_id, "rows": len(rows), "offset": offset})
    db.commit()
    return {"total": total, "items": [_feed_row(e, creds.get(e.id)) for e in rows]}


@app.get("/api/university/degree-feed.csv")
def degree_feed_csv(institution_id: int | None = None, db: Session = Depends(get_db),
                    user: User = Depends(require("UNIVERSITY"))):
    rows = db.scalars(_feed_query(db, user, institution_id, "").order_by(Enrolment.institution_id,
                                                                         Enrolment.roll_no)).all()
    creds = {c.enrolment_id: c for c in db.scalars(select(Credential).where(Credential.status == "ACTIVE"))}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["AICTE PID", "Institution", "Programme", "Student ID (roll no.)", "Name", "APAAR ID",
                "Provisional ID", "Year", "Verification QR payload"])
    for e in rows:
        r = _feed_row(e, creds.get(e.id))
        w.writerow([_cell(x) for x in (r["aicte_pid"], r["institution"], r["programme"], r["student_id"], r["name"],
                                       r["apaar_id"] or "", r["provisional_id"] or "", r["year_of_study"],
                                       r["qr_payload"] or "issue on request")])
    audit.record(db, user.username, user.role, "DEGREE_FEED_EXPORTED", "university", user.university,
                 {"institution_id": institution_id, "rows": len(rows)})
    db.commit()
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=degree_print_feed.csv"})


# --------------------------------------------------------------------------- audit
@app.get("/api/audit")
def audit_log(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), action: str = "",
              db: Session = Depends(get_db), _: User = Depends(require(*AICTE))):
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


@app.get("/api/audit/checkpoints")
def audit_checkpoints(limit: int = Query(10, ge=1, le=100), db: Session = Depends(get_db)):
    """Public: signed chain heads. Anyone may keep copies; a later rewrite of history will not match them."""
    rows = db.scalars(select(AuditCheckpoint).order_by(AuditCheckpoint.id.desc()).limit(limit)).all()
    return {"issuer": public_jwk(), "items": [audit.checkpoint_dict(c) for c in rows]}


@app.post("/api/audit/checkpoints")
def seal_now(db: Session = Depends(get_db), user: User = Depends(require("AICTE_ADMIN"))):
    cp = audit.checkpoint(db)
    db.commit()
    return audit.checkpoint_dict(cp)


@app.post("/api/audit/simulate")
def audit_simulate(attack: str = Body(embed=True), db: Session = Depends(get_db), _: User = Depends(require(*AICTE))):
    """Run an attack on an in-memory copy of the audit log; nothing stored is changed."""
    try:
        return audit.simulate(db, attack)
    except ValueError as ex:
        raise HTTPException(400, str(ex))


class ResetIn(BaseModel):
    pin: str = ""


@app.post("/api/demo/reset")
def demo_reset(request: Request, body: ResetIn | None = None, db: Session = Depends(get_db),
               user: User = Depends(require("AICTE_ADMIN"))):
    """DEMO ONLY: remove everything submitted through the portal so the walkthrough can be repeated.

    The audit trail is append-only, so it is kept and the reset itself is recorded in it.
    """
    _demo_only()
    limiter.check(request, "reset", 10)
    if config.DEMO_PIN and not hmac.compare_digest((body.pin if body else "").encode(), config.DEMO_PIN.encode()):
        raise HTTPException(403, "Demo PIN required to reset the shared demo")
    seeded_at = datetime.fromisoformat(db.get(Setting, "seeded_at").value)
    # Undo corrections made through the portal to seeded records, newest first.
    restored = 0
    for ev in db.scalars(select(AuditEvent).where(AuditEvent.action == "RECORD_UPDATED")
                         .order_by(AuditEvent.id.desc())):
        if ev.ts < seeded_at.astimezone().isoformat(timespec="seconds"):
            break
        e = db.get(Enrolment, int(ev.entity_id))
        if e is None or e.batch_id is not None:
            continue
        for field, old in (ev.details.get("before") or {}).items():
            if field in ("dob", "admission_date") and old:
                old = date.fromisoformat(old)
            setattr(e if field == "admission_date" else e.student, field, old)
        restored += 1
    enrol_ids = list(db.scalars(select(Enrolment.id).where(Enrolment.batch_id.is_not(None))))
    student_ids = set(db.scalars(select(Enrolment.student_id).where(Enrolment.id.in_(enrol_ids))))
    db.execute(delete(Credential).where(or_(Credential.enrolment_id.in_(enrol_ids), Credential.issued_at > seeded_at)))
    db.execute(update(Credential).values(status="ACTIVE", status_reason=None))
    db.execute(delete(Finding).where(or_(Finding.batch_id.is_not(None), Finding.enrolment_id.in_(enrol_ids),
                                         Finding.status != "OPEN")))
    db.execute(delete(Enrolment).where(Enrolment.id.in_(enrol_ids)))
    reopened = db.execute(update(Enrolment).where(Enrolment.status != "ACTIVE")
                          .values(status="ACTIVE", exit_date=None, exit_reason=None)).rowcount
    still_enrolled = set(db.scalars(select(Enrolment.student_id).where(Enrolment.student_id.in_(student_ids))))
    orphans = list(student_ids - still_enrolled)
    db.execute(delete(VerificationLog).where(or_(VerificationLog.student_id.in_(orphans),
                                                 VerificationLog.created_at > seeded_at)))
    db.execute(delete(ConsentRequest).where(or_(ConsentRequest.student_id.in_(orphans),
                                                ConsentRequest.created_at > seeded_at)))
    db.execute(delete(Student).where(Student.id.in_(orphans)))
    db.execute(delete(ApiKey))
    batches = db.execute(delete(UploadBatch)).rowcount
    result = services.refresh_national(db, user.username, user.role)
    audit.record(db, user.username, user.role, "DEMO_RESET", "dataset", "national",
                 {"removed_enrolments": len(enrol_ids), "removed_batches": batches, "reactivated": reopened,
                  "corrections_undone": restored})
    db.commit()
    events.publish("scan", result)
    return {"removed_enrolments": len(enrol_ids), "removed_students": len(orphans), "removed_batches": batches,
            "reactivated_enrolments": reopened}


# --------------------------------------------------------------------------- reports
@app.get("/api/reports/excess-intake.csv")
def report_excess(db: Session = Depends(get_db), user: User = Depends(require(*MONITOR))):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["AICTE PID", "Institution", "State", "Programme", "Approved intake", "Within-intake admitted",
                "Excess"])
    stmt = select(Institution).order_by(Institution.state)
    if _state_scope(user):
        stmt = stmt.where(Institution.state == user.state)
    for inst in db.scalars(stmt):
        for p in services.programme_ledger(db, inst.id):
            if p["excess"] > 0:
                w.writerow([_cell(x) for x in (inst.aicte_pid, inst.name, inst.state, p["name"],
                                                p["approved_intake"], p["within_intake"], p["excess"])])
    audit.record(db, user.username, user.role, "REPORT_DOWNLOADED", "report", "excess-intake", {})
    db.commit()
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=excess_intake_report.csv"})


@app.get("/api/reports/state-summary.xlsx")
def report_states(db: Session = Depends(get_db), user: User = Depends(require(*MONITOR))):
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
    ws2.append(["Rule", "Title", "Severity", "Open findings", "Distinct cases"])
    for code, n in sorted(d["findings_by_rule"].items()):
        ws2.append([code, RULES[code][1], RULES[code][0], n, d["cases_by_rule"].get(code, n)])
    ws3 = wb.create_sheet("Diversity")
    ws3.append(["Dimension", "Value", "Students"])
    for dim in ("gender", "category", "level"):
        for k, v in d[dim].items():
            ws3.append([dim, k, v])
    ws4 = wb.create_sheet("Ruleset")
    ws4.append(["Quota", "UG cap", "PG cap", "Diploma cap", "Verified", "Source"])
    for k, v in config.SUPERNUMERARY.items():
        ws4.append([k, v["caps"].get("UG"), v["caps"].get("PG"), v["caps"].get("DIPLOMA"), v["verified"], v["source"]])
    audit.record(db, user.username, user.role, "REPORT_DOWNLOADED", "report", "state-summary", {})
    db.commit()
    buf = io.BytesIO()
    wb.save(buf)
    return Response(buf.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": "attachment; filename=state_summary.xlsx"})


@app.get("/api/reports/institutions/{inst_id}/evidence.xlsx")
def evidence_pack(inst_id: int, db: Session = Depends(get_db), user: User = Depends(require(*AICTE))):
    """Evidence pack for a compliance review or show-cause notice: seat ledger, open findings, rules applied."""
    inst = db.get(Institution, inst_id) or _404("Institution")
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    for k, v in (("Institution", inst.name), ("AICTE PID", inst.aicte_pid), ("State", inst.state),
                 ("Affiliating university", inst.university or ""), ("Risk score", inst.risk_score),
                 ("Academic year", config.CURRENT_ACADEMIC_YEAR), ("Ruleset", config.RULESET_VERSION),
                 ("Generated", now().isoformat()), ("Penalty rule", config.RULESET["excess_admission_penalty"]["text"])):
        ws.append([k, _cell(v)])
    ws.append([])
    ws.append(["Why this score"])
    for r in inst.risk_reasons or []:
        ws.append([r["text"]])
    ws2 = wb.create_sheet("Seat ledger")
    ws2.append(["Programme", "Level", "Approved intake", "Within intake", "Excess",
                *[f"{k} used/cap" for k in config.SUPERNUMERARY_TYPES]])
    for p in services.programme_ledger(db, inst_id):
        ws2.append([p["name"], p["level"], p["approved_intake"], p["within_intake"], p["excess"],
                    *[f"{p['supernumerary'][k]['used']}/{p['supernumerary'][k]['cap']}" for k in config.SUPERNUMERARY_TYPES]])
    ws3 = wb.create_sheet("Open findings")
    ws3.append(["#", "Rule", "Severity", "Message", "Rule version", "Raised"])
    for f in db.scalars(select(Finding).where(Finding.institution_id == inst_id, Finding.status == "OPEN")
                        .order_by(Finding.rule_code)):
        ws3.append([f.id, f.rule_code, f.severity, _cell(f.message), f.rule_version, f.created_at.isoformat()])
    audit.record(db, user.username, user.role, "EVIDENCE_PACK_DOWNLOADED", "institution", inst_id, {})
    db.commit()
    buf = io.BytesIO()
    wb.save(buf)
    return Response(buf.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename=evidence_{inst.aicte_pid}.xlsx"})


def _cell(v):
    """Neutralise spreadsheet formulas in exported text (CSV / Excel injection)."""
    return "'" + v if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r") else v


def _404(what: str):
    raise HTTPException(404, f"{what} not found")


# --------------------------------------------------------------------------- frontend
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        # Resolve and confine to the build folder so "../" cannot reach the data directory.
        f = (DIST / path).resolve()
        if path and f.is_file() and f.is_relative_to(DIST.resolve()):
            headers = {"Cache-Control": "no-cache"} if f.name in ("sw.js", "manifest.webmanifest") else None
            return FileResponse(f, headers=headers)
        return HTMLResponse((DIST / "index.html").read_text(), headers={"Cache-Control": "no-cache"})
