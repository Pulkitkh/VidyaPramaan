from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now() -> datetime:
    return datetime.now().replace(microsecond=0)


class Institution(Base):
    __tablename__ = "institution"
    id: Mapped[int] = mapped_column(primary_key=True)
    aicte_pid: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(60), index=True)
    city: Mapped[str] = mapped_column(String(80))
    region: Mapped[str] = mapped_column(String(30))
    inst_type: Mapped[str] = mapped_column(String(40))
    university: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)  # affiliating body
    risk_score: Mapped[float] = mapped_column(Float, default=0)
    risk_reasons: Mapped[list] = mapped_column(JSON, default=list)
    quality_score: Mapped[float] = mapped_column(Float, default=100)
    programmes: Mapped[list["Programme"]] = relationship(back_populates="institution")


class Programme(Base):
    __tablename__ = "programme"
    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institution.id"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    level: Mapped[str] = mapped_column(String(10))  # UG | PG | DIPLOMA
    name: Mapped[str] = mapped_column(String(120))
    academic_year: Mapped[str] = mapped_column(String(10))
    approved_intake: Mapped[int] = mapped_column(Integer)
    institution: Mapped[Institution] = relationship(back_populates="programmes")


class Student(Base):
    __tablename__ = "student"
    id: Mapped[int] = mapped_column(primary_key=True)
    apaar_id: Mapped[str | None] = mapped_column(String(12), index=True, nullable=True)
    provisional_id: Mapped[str | None] = mapped_column(String(24), nullable=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    dob: Mapped[date] = mapped_column(Date, index=True)
    gender: Mapped[str] = mapped_column(String(1))
    category: Mapped[str] = mapped_column(String(10))
    # At least one of father / mother / guardian is required; none of them is mandatory on its own.
    father_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    mother_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    guardian_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(15), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    nationality: Mapped[str] = mapped_column(String(40), default="Indian")
    fn_status: Mapped[bool] = mapped_column(Boolean, default=False)
    oci_status: Mapped[bool] = mapped_column(Boolean, default=False)
    oci_card_no: Mapped[str | None] = mapped_column(String(20), nullable=True)
    passport_no: Mapped[str | None] = mapped_column(String(20), nullable=True)
    nri_status: Mapped[bool] = mapped_column(Boolean, default=False)
    nri_country: Mapped[str | None] = mapped_column(String(40), nullable=True)
    pwd: Mapped[bool] = mapped_column(Boolean, default=False)
    apaar_consent: Mapped[str] = mapped_column(String(14), default="GIVEN")  # GIVEN | REFUSED | NOT_RECORDED


class Enrolment(Base):
    __tablename__ = "enrolment"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"), index=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institution.id"), index=True)
    programme_id: Mapped[int] = mapped_column(ForeignKey("programme.id"), index=True)
    roll_no: Mapped[str] = mapped_column(String(30))
    admission_year: Mapped[int] = mapped_column(Integer)
    year_of_study: Mapped[int] = mapped_column(Integer, default=1)
    admission_type: Mapped[str] = mapped_column(String(10))  # REGULAR | LATERAL
    quota: Mapped[str] = mapped_column(String(20))
    seat_type: Mapped[str] = mapped_column(String(15))  # WITHIN_INTAKE | SUPERNUMERARY
    supernumerary_type: Mapped[str | None] = mapped_column(String(15), nullable=True)
    admission_date: Mapped[date] = mapped_column(Date)
    # ACTIVE | WITHDRAWN | TRANSFERRED_OUT | GRADUATED | DROPPED
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", index=True)
    exit_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("upload_batch.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    student: Mapped[Student] = relationship()
    programme: Mapped[Programme] = relationship()
    institution: Mapped[Institution] = relationship()


class UploadBatch(Base):
    __tablename__ = "upload_batch"
    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institution.id"), index=True)
    filename: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(10), default="CSV")  # CSV | API
    uploaded_by: Mapped[str] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    status: Mapped[str] = mapped_column(String(12), default="VALIDATED")
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, default=0)
    warning_rows: Mapped[int] = mapped_column(Integer, default=0)
    committed_rows: Mapped[int] = mapped_column(Integer, default=0)
    rows: Mapped[list] = mapped_column(JSON, default=list)
    column_map: Mapped[dict] = mapped_column(JSON, default=dict)
    idempotency_key: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    row_results: Mapped[list] = mapped_column(JSON, default=list)


class Finding(Base):
    __tablename__ = "finding"
    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institution.id"), index=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("upload_batch.id"), nullable=True)
    enrolment_id: Mapped[int | None] = mapped_column(ForeignKey("enrolment.id"), nullable=True)
    programme_id: Mapped[int | None] = mapped_column(ForeignKey("programme.id"), nullable=True)
    related_institution_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(8), default="BATCH")  # BATCH | SCAN
    rule_code: Mapped[str] = mapped_column(String(10), index=True)
    severity: Mapped[str] = mapped_column(String(8), index=True)
    message: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    rule_version: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(10), default="OPEN", index=True)
    # Stable identity of what was found (rule + records involved). Reviewer decisions are remembered
    # by fingerprint, so a dismissed item does not come back on the next national scan.
    fingerprint: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(60), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    institution: Mapped[Institution] = relationship(foreign_keys=[institution_id])


class MockApaarRecord(Base):
    """Stand-in for the national APAAR/ABC registry (see apaar_registry.py)."""
    __tablename__ = "mock_apaar_registry"
    apaar_id: Mapped[str] = mapped_column(String(12), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    dob: Mapped[date] = mapped_column(Date)
    gender: Mapped[str] = mapped_column(String(1))
    status: Mapped[str] = mapped_column(String(12), default="ACTIVE")


class ConsentRequest(Base):
    __tablename__ = "consent_request"
    id: Mapped[int] = mapped_column(primary_key=True)
    # Null when no record exists for the APAAR ID: the request is kept and simply never answered,
    # so a verifier cannot use consent requests to probe who is in the registry.
    student_id: Mapped[int | None] = mapped_column(ForeignKey("student.id"), index=True, nullable=True)
    apaar_masked: Mapped[str] = mapped_column(String(20), default="")
    verifier_org: Mapped[str] = mapped_column(String(120))
    verifier_user: Mapped[str] = mapped_column(String(60))
    purpose: Mapped[str] = mapped_column(String(200))
    scope: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(10), default="PENDING")  # PENDING|APPROVED|DENIED|REVOKED|EXPIRED|LOCKED
    otp_hash: Mapped[str] = mapped_column(String(64))
    demo_otp: Mapped[str | None] = mapped_column(String(6), nullable=True)  # kept only in demo mode
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime)  # request expiry, then access-window expiry once approved
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class VerificationLog(Base):
    __tablename__ = "verification_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"), index=True)
    consent_id: Mapped[int | None] = mapped_column(ForeignKey("consent_request.id"), nullable=True)
    verifier_org: Mapped[str] = mapped_column(String(120))
    basis: Mapped[str] = mapped_column(String(20))  # CONSENT | STATUTORY | CREDENTIAL
    purpose: Mapped[str] = mapped_column(String(200))
    disclosed: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Credential(Base):
    __tablename__ = "credential"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"), index=True)
    enrolment_id: Mapped[int] = mapped_column(ForeignKey("enrolment.id"))
    vc: Mapped[dict] = mapped_column(JSON)
    token: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="ACTIVE")  # ACTIVE | SUPERSEDED | REVOKED
    status_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class AuditEvent(Base):
    __tablename__ = "audit_event"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[str] = mapped_column(String(25))
    actor: Mapped[str] = mapped_column(String(60))
    role: Mapped[str] = mapped_column(String(30))
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(50))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))


class AuditCheckpoint(Base):
    """Signed snapshot of the audit chain head. Published copies make a silent rewrite of history,
    or truncation of its tail, detectable even by someone who can recompute every hash."""
    __tablename__ = "audit_checkpoint"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[str] = mapped_column(String(32))
    event_count: Mapped[int] = mapped_column(Integer)
    head_event_id: Mapped[int] = mapped_column(Integer)
    head_hash: Mapped[str] = mapped_column(String(64))
    signature: Mapped[str] = mapped_column(Text)


class ApiKey(Base):
    """Per-institution key for ERP integration. Only a hash is stored; the key is shown once."""
    __tablename__ = "api_key"
    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institution.id"), index=True)
    label: Mapped[str] = mapped_column(String(80))
    prefix: Mapped[str] = mapped_column(String(12), index=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class Setting(Base):
    __tablename__ = "setting"
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
