"""Tamper-evident audit trail.

Each event stores sha256(prev_hash + canonical event body). Changing or deleting
any past row breaks every hash after it, which verify_chain() detects.
"""
import hashlib
import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AuditEvent

GENESIS = "0" * 64


def _digest(prev_hash: str, ts: str, actor: str, role: str, action: str,
            entity: str, entity_id: str, details: dict) -> str:
    body = json.dumps(
        [ts, actor, role, action, entity, entity_id, details],
        sort_keys=True, separators=(",", ":"), default=str,
    )
    return hashlib.sha256((prev_hash + body).encode()).hexdigest()


def record(db: Session, actor: str, role: str, action: str, entity: str,
           entity_id, details: dict | None = None) -> AuditEvent:
    last = db.scalars(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1)).first()
    prev_hash = last.hash if last else GENESIS
    ts = datetime.now().isoformat(timespec="seconds")
    details = details or {}
    ev = AuditEvent(
        ts=ts, actor=actor, role=role, action=action, entity=entity,
        entity_id=str(entity_id), details=details, prev_hash=prev_hash,
        hash=_digest(prev_hash, ts, actor, role, action, entity, str(entity_id), details),
    )
    db.add(ev)
    db.flush()
    return ev


def verify_chain(db: Session) -> dict:
    prev = GENESIS
    count = 0
    for ev in db.scalars(select(AuditEvent).order_by(AuditEvent.id)):
        count += 1
        expected = _digest(prev, ev.ts, ev.actor, ev.role, ev.action, ev.entity, ev.entity_id, ev.details)
        if ev.prev_hash != prev or ev.hash != expected:
            return {"valid": False, "checked": count, "broken_at": ev.id,
                    "expected_hash": expected, "stored_hash": ev.hash}
        prev = ev.hash
    return {"valid": True, "checked": count, "head": prev}
