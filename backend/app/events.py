"""In-process event fan-out for the live dashboards (Server-Sent Events)."""
import asyncio
import json

_subscribers: set[asyncio.Queue] = set()


def publish(kind: str, payload: dict) -> None:
    msg = json.dumps({"type": kind, **payload}, default=str)
    for q in list(_subscribers):
        try:
            q.put_nowait(msg)
        except asyncio.QueueFull:
            pass


async def stream():
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers.add(q)
    try:
        yield "event: hello\ndata: {}\n\n"
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=15)
                yield f"data: {msg}\n\n"
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
    finally:
        _subscribers.discard(q)
