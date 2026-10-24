"""In-process event fan-out for the live dashboards (Server-Sent Events).

Each event names its audience, and a subscriber receives only events meant for its role or
identity: national monitoring roles see national activity, an institution sees its own, a
student sees their own consent requests. Publishing is thread-safe because sync endpoints run
in a thread pool while the queues belong to the event loop.
"""
import asyncio
import json

from .auth import User

MONITOR_ROLES = {"AICTE_ADMIN", "AUDITOR", "REGULATOR"}
_subscribers: dict[asyncio.Queue, tuple[User, asyncio.AbstractEventLoop]] = {}


def _allowed(user: User, roles: set[str], institution_id, student_id, username) -> bool:
    return (user.role in roles or (institution_id is not None and user.institution_id == institution_id)
            or (student_id is not None and user.student_id == student_id)
            or (username is not None and user.username == username))


def publish(kind: str, payload: dict, *, roles: set[str] = MONITOR_ROLES, institution_id: int | None = None,
            student_id: int | None = None, username: str | None = None) -> None:
    msg = json.dumps({"type": kind, **payload}, default=str)
    for q, (user, loop) in list(_subscribers.items()):
        if not _allowed(user, roles, institution_id, student_id, username):
            continue
        try:
            loop.call_soon_threadsafe(_put, q, msg)
        except RuntimeError:  # loop closed
            _subscribers.pop(q, None)


def _put(q: asyncio.Queue, msg: str) -> None:
    try:
        q.put_nowait(msg)
    except asyncio.QueueFull:
        pass


async def stream(user: User):
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers[q] = (user, asyncio.get_running_loop())
    try:
        yield "event: hello\ndata: {}\n\n"
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=15)
                yield f"data: {msg}\n\n"
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
    finally:
        _subscribers.pop(q, None)
