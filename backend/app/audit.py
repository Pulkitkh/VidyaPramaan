"""Tamper-evident audit trail.

Each event stores sha256(prev_hash + canonical event body), so changing or
deleting any past row breaks every hash after it. A hash chain alone has a
known gap: someone with database access can edit a row and then recompute every
later hash, or quietly drop the newest events. Signed checkpoints close it. After
each national scan the chain head (event count, last id, last hash) is signed
with the issuer's Ed25519 key and published at /api/audit/checkpoints. A
rewritten or truncated chain no longer matches a checkpoint someone already holds.
"""
import copy
import hashlib
import json
import logging
import threading
from datetime import datetime, timezone

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from .models import AuditCheckpoint, AuditEvent

GENESIS = "0" * 64
log = logging.getLogger("vidyapramaan.audit")

# Appending reads the last hash and inserts after it; two writers interleaving would fork the chain.
# The lock is held from the first append in a transaction until that transaction ends.
_LOCK = threading.Lock()


@event.listens_for(Session, "after_transaction_end")
def _release(session, transaction):
    if transaction.parent is None and session.info.pop("audit_lock", False):
        _LOCK.release()


def _acquire(db: Session) -> None:
    if db.info.get("audit_lock"):
        return
    if not _LOCK.acquire(timeout=15):
        log.error("audit lock wait timed out; appending without it")
        return
    db.info["audit_lock"] = True


def _digest(prev_hash: str, ts: str, actor: str, role: str, action: str,
            entity: str, entity_id: str, details: dict) -> str:
    body = json.dumps(
        [ts, actor, role, action, entity, entity_id, details],
        sort_keys=True, separators=(",", ":"), default=str,
    )
    return hashlib.sha256((prev_hash + body).encode()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def record(db: Session, actor: str, role: str, action: str, entity: str,
           entity_id, details: dict | None = None) -> AuditEvent:
    _acquire(db)
    last = db.scalars(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1)).first()
    prev_hash = last.hash if last else GENESIS
    ts = _now()
    details = json.loads(json.dumps(details or {}, default=str))
    ev = AuditEvent(
        ts=ts, actor=actor, role=role, action=action, entity=entity,
        entity_id=str(entity_id), details=details, prev_hash=prev_hash,
        hash=_digest(prev_hash, ts, actor, role, action, entity, str(entity_id), details),
    )
    db.add(ev)
    db.flush()
    return ev


def _payload(count: int, head_id: int, head_hash: str, ts: str) -> dict:
    return {"type": "audit-checkpoint", "count": count, "head_event_id": head_id, "head_hash": head_hash, "ts": ts}


def checkpoint(db: Session) -> AuditCheckpoint | None:
    from .credentials import sign_compact
    _acquire(db)
    last = db.scalars(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1)).first()
    if last is None:
        return None
    count = db.query(AuditEvent).count()
    ts = _now()
    cp = AuditCheckpoint(ts=ts, event_count=count, head_event_id=last.id, head_hash=last.hash,
                         signature=sign_compact(_payload(count, last.id, last.hash, ts)))
    db.add(cp)
    db.flush()
    return cp


def checkpoint_dict(cp: AuditCheckpoint) -> dict:
    return {"id": cp.id, "ts": cp.ts, "event_count": cp.event_count, "head_event_id": cp.head_event_id,
            "head_hash": cp.head_hash, "signature": cp.signature}


def _rows(db: Session) -> list[dict]:
    return [{"id": e.id, "ts": e.ts, "actor": e.actor, "role": e.role, "action": e.action, "entity": e.entity,
             "entity_id": e.entity_id, "details": e.details, "prev_hash": e.prev_hash, "hash": e.hash}
            for e in db.scalars(select(AuditEvent).order_by(AuditEvent.id))]


def _check(rows: list[dict], checkpoints: list[AuditCheckpoint]) -> dict:
    from .credentials import verify_compact
    prev = GENESIS
    for n, ev in enumerate(rows, 1):
        expected = _digest(prev, ev["ts"], ev["actor"], ev["role"], ev["action"], ev["entity"], ev["entity_id"],
                           ev["details"])
        if ev["prev_hash"] != prev or ev["hash"] != expected:
            return {"valid": False, "checked": n, "broken_at": ev["id"], "reason": "hash_mismatch",
                    "expected_hash": expected, "stored_hash": ev["hash"]}
        prev = ev["hash"]
    by_id = {r["id"]: (i + 1, r) for i, r in enumerate(rows)}
    anchors = 0
    for cp in checkpoints:
        ok, claims = verify_compact(cp.signature)
        if not ok or claims != _payload(cp.event_count, cp.head_event_id, cp.head_hash, cp.ts):
            return {"valid": False, "checked": len(rows), "reason": "checkpoint_signature_invalid",
                    "checkpoint": cp.id}
        pos = by_id.get(cp.head_event_id)
        if pos is None or pos[0] != cp.event_count:
            return {"valid": False, "checked": len(rows), "reason": "events_missing", "checkpoint": cp.id,
                    "checkpoint_count": cp.event_count, "head_event_id": cp.head_event_id,
                    "found_count": pos[0] if pos else len(rows)}
        if pos[1]["hash"] != cp.head_hash:
            return {"valid": False, "checked": len(rows), "reason": "history_rewritten", "checkpoint": cp.id,
                    "broken_at": cp.head_event_id, "expected_hash": cp.head_hash, "stored_hash": pos[1]["hash"]}
        anchors += 1
    return {"valid": True, "checked": len(rows), "head": prev, "checkpoints_verified": anchors,
            "latest_checkpoint": checkpoints[-1].ts if checkpoints else None}


def verify_chain(db: Session) -> dict:
    return _check(_rows(db), list(db.scalars(select(AuditCheckpoint).order_by(AuditCheckpoint.id))))


def simulate(db: Session, attack: str) -> dict:
    """Run an attack on an in-memory copy of the log and report what verification sees.

    Nothing is written, so the shared demo can never be left in a tampered state.
      edit      change one past event (a rogue DBA editing a row)
      rewrite   change it and recompute every later hash (a careful attacker)
      truncate  delete the newest events covered by the latest checkpoint
    """
    rows = copy.deepcopy(_rows(db))
    cps = list(db.scalars(select(AuditCheckpoint).order_by(AuditCheckpoint.id)))
    if len(rows) < 3:
        return {"attack": attack, "applied": False}
    target = next((r for r in rows if r["action"] == "UPLOAD_COMMITTED"), rows[1])
    note = ""
    if attack in ("edit", "rewrite"):
        target["details"] = {**target["details"], "rejected": 0, "note": "edited directly in the database"}
        note = f"event #{target['id']} ({target['action']}) edited"
        if attack == "rewrite":
            i = rows.index(target)
            prev = rows[i - 1]["hash"] if i else GENESIS
            for r in rows[i:]:
                r["prev_hash"] = prev
                r["hash"] = _digest(prev, r["ts"], r["actor"], r["role"], r["action"], r["entity"], r["entity_id"],
                                    r["details"])
                prev = r["hash"]
            note += ", then every later hash recomputed"
    elif attack == "truncate":
        head = cps[-1].head_event_id if cps else rows[-1]["id"]
        keep = [r for r in rows if r["id"] < head - 2]
        note = f"{len(rows) - len(keep)} newest events deleted"
        rows = keep
    else:
        raise ValueError("attack must be edit, rewrite or truncate")
    plain = _check(rows, [])
    anchored = _check(rows, cps)
    return {"attack": attack, "applied": True, "what": note, "chain_only": plain, "with_checkpoints": anchored}
