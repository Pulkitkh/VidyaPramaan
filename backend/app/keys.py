"""Issuer key bookkeeping: detect a rotated key at startup and re-sign what the old key signed.

The demo database is built before the deployment's secret is known, and a real issuer rotates
keys too. A rotation is not hidden: every credential and audit checkpoint is re-signed with the
new key and the rotation itself is written to the audit trail.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import audit
from .credentials import key_id, resign_token, resign_vc, sign_compact
from .models import AuditCheckpoint, Credential, Setting


def record_key(db: Session) -> None:
    s = db.get(Setting, "issuer_kid")
    if s is None:
        db.add(Setting(key="issuer_kid", value=key_id()))
    else:
        s.value = key_id()


def ensure_current_key(db: Session) -> dict | None:
    s = db.get(Setting, "issuer_kid")
    current = key_id()
    if s is not None and s.value == current:
        return None
    creds = cps = 0
    for c in db.scalars(select(Credential)):
        c.token = resign_token(c.token)
        c.vc = resign_vc(c.vc)
        creds += 1
    for cp in db.scalars(select(AuditCheckpoint)):
        cp.signature = sign_compact(audit._payload(cp.event_count, cp.head_event_id, cp.head_hash, cp.ts))
        cps += 1
    old = s.value if s else None
    record_key(db)
    result = {"old_key": old, "new_key": current, "credentials_resigned": creds, "checkpoints_resigned": cps}
    audit.record(db, "system", "SYSTEM", "ISSUER_KEY_ROTATED", "issuer", current, result)
    audit.checkpoint(db)
    db.commit()
    return result
