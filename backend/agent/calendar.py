"""Turning a scheduled interview into a Google Calendar event.

Everything here is pure except `create_event`, so the shape of what gets sent
to Google — and what gets read back — is testable without a live MCP server.
"""

import base64
import binascii
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger("jcc.calendar")

#: The tool workspace-mcp exposes for calendar writes. It is one tool for
#: create/update/delete/RSVP, switched by its `action` argument.
EVENT_TOOL = "manage_event"

#: Asia/Kolkata as a fixed offset rather than a `ZoneInfo`. Windows ships no
#: IANA database and `tzdata` is not a dependency here, so `ZoneInfo` raises
#: `ZoneInfoNotFoundError` on this machine. India has had no DST since 1945,
#: so a fixed offset is exact — and the IANA name still goes to Google below,
#: which is what makes the event display in the right zone.
IST = timezone(timedelta(hours=5, minutes=30))
IST_NAME = "Asia/Kolkata"

#: How long an interview is assumed to run when nobody says otherwise.
DEFAULT_DURATION_MINUTES = 45

#: A follow-up is a nudge, not a meeting, so it takes a token slot.
REMINDER_DURATION_MINUTES = 15


def _slot(when: str, duration_minutes: int) -> tuple[str, str] | None:
    """Start and end as ISO strings Google cannot misread, or None if `when` is
    not a datetime at all."""
    try:
        start = datetime.fromisoformat(when)
    except (TypeError, ValueError):
        # The model is told to pass ISO 8601. When it passes "next Tuesday"
        # instead, booking nothing beats booking the wrong hour.
        logger.warning("cannot place a calendar event at unparseable time %r", when)
        return None

    # A bare timestamp is read by Google in the calendar's own default zone,
    # which is not necessarily this user's.
    if start.tzinfo is None:
        start = start.replace(tzinfo=IST)
    return start.isoformat(), (start + timedelta(minutes=duration_minutes)).isoformat()


def build_event(job, when: str, round_label: str,
                duration_minutes: int = DEFAULT_DURATION_MINUTES) -> dict | None:
    """The `manage_event` arguments for one interview, or None if `when` is not
    a datetime we can place on a calendar."""
    slot = _slot(when, duration_minutes)
    if slot is None:
        return None
    start, end = slot
    round_name = round_label.replace("_", " ").title()

    return {
        "action": "create",
        "summary": f"Interview: {job['title']} at {job['company']}",
        "start_time": start,
        "end_time": end,
        "timezone": IST_NAME,
        "description": (f"{round_name} for {job['title']} at {job['company']}.\n"
                        f"Job #{job['id']} in Job Command Center."),
    }


def build_reminder(job, when: str, about: str,
                   duration_minutes: int = REMINDER_DURATION_MINUTES) -> dict | None:
    """The `manage_event` arguments for a follow-up nudge, or None if `when` is
    not a datetime we can place on a calendar."""
    slot = _slot(when, duration_minutes)
    if slot is None:
        return None
    start, end = slot

    return {
        "action": "create",
        "summary": f"Follow up: {job['title']} at {job['company']}",
        "start_time": start,
        "end_time": end,
        "timezone": IST_NAME,
        "description": (f"{about}\n\n"
                        f"Job #{job['id']} in Job Command Center."),
        # An override is also what stops Google applying the calendar's default
        # reminders, which are tuned for meetings, not nudges.
        "reminders": [{"method": "popup", "minutes": 0}],
    }


async def create_event(server, event: dict) -> str:
    """Run `manage_event` on the MCP server and return its confirmation text.

    Goes through the server's own tool list rather than its private client, so
    this keeps working if the SDK changes how it talks to MCP.
    """
    tools = await server.list_tools()
    tool = next((t for t in tools if t.info.name == EVENT_TOOL), None)
    if tool is None:
        raise LookupError(
            f"the MCP server exposes no {EVENT_TOOL} tool; "
            "is workspace-mcp running with --tools calendar?")
    return await tool(event)


def _text(response) -> str:
    """The prose inside whatever `manage_event` handed back.

    The SDK resolves an MCP result to `content[0].model_dump_json()`, so what
    arrives is a JSON envelope — `{"type":"text","text":"...","meta":null}` —
    not the message itself. Plain strings are passed through, because that is
    what a differently-configured resolver would produce.
    """
    if not isinstance(response, str):
        return str(response or "")
    try:
        loaded = json.loads(response)
    except (ValueError, TypeError):
        return response
    if isinstance(loaded, dict):
        return str(loaded.get("text") or response)
    if isinstance(loaded, list):
        return " ".join(str(p.get("text", "")) for p in loaded
                        if isinstance(p, dict)) or response
    return response


def parse_event_link(response: str) -> str | None:
    """The event URL out of a `manage_event` confirmation."""
    # Matched as URL characters rather than as non-whitespace: inside the JSON
    # envelope the link is followed immediately by `","annotations"...` with no
    # space, and \S+ swallows all of it.
    match = re.search(r"Link:\s*(https?://[^\s\"'\\<>]+)", _text(response))
    return match.group(1).rstrip(".,;") if match else None


def parse_event_id(response: str) -> str | None:
    """The Google event id out of a `manage_event` confirmation.

    `manage_event` returns prose and logs the id without returning it, so the
    only copy that reaches us is the base64 `eid` in the link it quotes, which
    packs "<event id> <calendar id>".
    """
    link = parse_event_link(response)
    if not link:
        return None
    eid = (parse_qs(urlparse(link).query).get("eid") or [None])[0]
    # Checked before decoding: b64decode silently discards characters outside
    # the alphabet, so junk would otherwise decode to plausible-looking bytes.
    if not eid or not re.fullmatch(r"[A-Za-z0-9_-]+", eid):
        return None
    try:
        decoded = base64.urlsafe_b64decode(eid + "=" * (-len(eid) % 4)).decode()
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None
    event_id = decoded.split(" ")[0]
    return event_id if re.fullmatch(r"[A-Za-z0-9_-]+", event_id) else None
