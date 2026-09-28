"""The wire format of Server-Sent Events: three lines and a blank one.

No dependency added for this. sse-starlette is the kind of package a
dependency review gates, and what it would save here is three string lines: `event:`, an
optional `id:`, `data:`, then a blank line that marks where one message
ends and the next begins. That is the whole format. Writing it by hand
costs less than reviewing a dependency for it.
"""

from __future__ import annotations

# A comment line: EventSource ignores it as an event, but it is still a
# byte on the wire, which is what keeps a proxy that treats a silent
# connection as idle from closing it out from under a run still in queue.
KEEPALIVE = ": keepalive\n\n"


def format_event(event: str, data: str, event_id: str | None = None) -> str:
    """Render one SSE message: an event name, an optional id, and its data.

    `data` arrives already serialized (json.dumps, or a pydantic model's
    own): this function only knows the wire format, not what the payload
    means. `event_id` becomes the message's `id:` line, which is what lets
    a reconnecting EventSource say `Last-Event-ID` (unused by this route
    today, but free to add later because the format already carries it).
    """
    lines = [f"event: {event}"]
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"data: {data}")
    return "\n".join(lines) + "\n\n"
