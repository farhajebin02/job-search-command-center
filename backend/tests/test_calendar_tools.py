"""The two tools that write to the user's real Google Calendar.

schedule_interview must land in two places -- the calendar and the local
pipeline -- so these cover what happens when only one of them works.
set_reminder writes to the calendar only, so a failure there means nothing
happened at all, and it must say so rather than borrow the softer wording."""

import base64
import json

import pytest

from core.db import connect, init_db
from core import tracker


def _confirmation(event_id: str, calendar_id: str = "farhajebin02@gmail.com") -> str:
    """What manage_event actually hands back: prose wrapped in the JSON
    envelope the SDK resolves MCP results into, with the link running straight
    into a quote. Built this way because a hand-written plain-text fixture let
    a broken parser pass these tests while failing against real Google."""
    eid = base64.urlsafe_b64encode(
        f"{event_id} {calendar_id}".encode()).decode().rstrip("=")
    link = f"https://www.google.com/calendar/event?eid={eid}"
    return json.dumps({
        "type": "text",
        "text": f"Successfully created event 'x' for {calendar_id}. Link: {link}",
        "annotations": None, "meta": None,
    })


class _FakeParticipant:
    def __init__(self):
        self.published = []

    async def publish_data(self, data, reliable=True):
        self.published.append(json.loads(data.decode()))


class _FakeRoom:
    def __init__(self):
        self.local_participant = _FakeParticipant()

    def on(self, event, callback):
        pass


class _FakeToolInfo:
    def __init__(self, name):
        self.name = name


class _FakeTool:
    def __init__(self, name, result="ok"):
        self.info = _FakeToolInfo(name)
        self.result = result
        self.calls = []

    async def __call__(self, args):
        self.calls.append(args)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class _FakeServer:
    def __init__(self, tool):
        self.tool = tool

    async def list_tools(self):
        return [self.tool]


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = str(tmp_path / "t.db")
    monkeypatch.setenv("DB_PATH", path)
    seed = connect(path)
    init_db(seed)
    seed.execute("INSERT INTO job (source, source_id, title, company, location, "
                 "apply_url) VALUES ('seed','s1','Backend Engineer',"
                 "'Freshworks','Chennai','u')")
    seed.commit()
    tracker.mark_applied(seed, 1)
    seed.close()
    return path


def _pilot(room=None, calendar_server=None):
    from agent.personas import CoPilot
    return CoPilot(room or _FakeRoom(), calendar=calendar_server)


def _interviews(db_path):
    conn = connect(db_path)
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM interview")]
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_scheduling_creates_a_real_calendar_event(db_path):
    tool = _FakeTool("manage_event", _confirmation("abc123def"))
    pilot = _pilot(calendar_server=_FakeServer(tool))

    await pilot.schedule_interview(None, 1, "2026-08-18T15:00:00")

    assert len(tool.calls) == 1
    assert tool.calls[0]["action"] == "create"
    assert tool.calls[0]["summary"] == "Interview: Backend Engineer at Freshworks"
    assert tool.calls[0]["start_time"] == "2026-08-18T15:00:00+05:30"


@pytest.mark.asyncio
async def test_scheduling_stores_the_google_event_id_on_the_interview(db_path):
    tool = _FakeTool("manage_event", _confirmation("abc123def"))
    pilot = _pilot(calendar_server=_FakeServer(tool))

    await pilot.schedule_interview(None, 1, "2026-08-18T15:00:00")

    assert _interviews(db_path)[0]["calendar_event_id"] == "abc123def"


@pytest.mark.asyncio
async def test_a_failed_calendar_write_still_records_the_interview(db_path):
    # Google being unreachable must not cost the user their pipeline entry.
    tool = _FakeTool("manage_event", RuntimeError("token expired"))
    pilot = _pilot(calendar_server=_FakeServer(tool))

    await pilot.schedule_interview(None, 1, "2026-08-18T15:00:00")

    rows = _interviews(db_path)
    assert len(rows) == 1
    assert rows[0]["calendar_event_id"] is None


@pytest.mark.asyncio
async def test_a_failed_calendar_write_tells_the_model_to_say_so(db_path):
    # Silence here would have the agent claim an event exists when it does not.
    tool = _FakeTool("manage_event", RuntimeError("token expired"))
    pilot = _pilot(calendar_server=_FakeServer(tool))

    said = await pilot.schedule_interview(None, 1, "2026-08-18T15:00:00")

    assert "calendar" in said.lower()
    assert "not" in said.lower()


@pytest.mark.asyncio
async def test_a_failed_calendar_write_is_logged(db_path, caplog):
    tool = _FakeTool("manage_event", RuntimeError("token expired"))
    pilot = _pilot(calendar_server=_FakeServer(tool))

    with caplog.at_level("ERROR"):
        await pilot.schedule_interview(None, 1, "2026-08-18T15:00:00")

    assert "token expired" in caplog.text


@pytest.mark.asyncio
async def test_an_unknown_job_reaches_neither_google_nor_the_database(db_path):
    tool = _FakeTool("manage_event")
    pilot = _pilot(calendar_server=_FakeServer(tool))

    said = await pilot.schedule_interview(None, 999, "2026-08-18T15:00:00")

    assert tool.calls == []
    assert _interviews(db_path) == []
    assert "no job with id 999" in said


@pytest.mark.asyncio
async def test_an_unparseable_time_keeps_the_interview_off_the_calendar(db_path):
    # "next Tuesday" booked literally is worse than no event at all.
    tool = _FakeTool("manage_event")
    pilot = _pilot(calendar_server=_FakeServer(tool))

    await pilot.schedule_interview(None, 1, "next Tuesday")

    assert tool.calls == []


@pytest.mark.asyncio
async def test_scheduling_works_when_no_calendar_is_configured(db_path):
    # The agent must still run if workspace-mcp failed to start.
    pilot = _pilot(calendar_server=None)

    await pilot.schedule_interview(None, 1, "2026-08-18T15:00:00")

    assert len(_interviews(db_path)) == 1


@pytest.mark.asyncio
async def test_scheduling_still_tells_the_ui_an_interview_landed(db_path):
    room = _FakeRoom()
    tool = _FakeTool("manage_event", _confirmation("abc123def"))
    pilot = _pilot(room=room, calendar_server=_FakeServer(tool))

    await pilot.schedule_interview(None, 1, "2026-08-18T15:00:00")

    assert any(e["type"] == "interview.scheduled"
               for e in room.local_participant.published)


# ---- set_reminder -----------------------------------------------------

@pytest.mark.asyncio
async def test_a_reminder_lands_on_the_calendar_as_a_follow_up(db_path):
    tool = _FakeTool("manage_event", _confirmation("rem123"))
    pilot = _pilot(calendar_server=_FakeServer(tool))

    await pilot.set_reminder(None, 1, "2026-08-21T10:00:00", "email the recruiter")

    assert len(tool.calls) == 1
    assert tool.calls[0]["summary"] == "Follow up: Backend Engineer at Freshworks"
    assert tool.calls[0]["reminders"] == [{"method": "popup", "minutes": 0}]


@pytest.mark.asyncio
async def test_a_reminder_does_not_create_an_interview(db_path):
    # A follow-up nudge is not an interview round; putting it in that table
    # would show a phantom interview on the pipeline.
    tool = _FakeTool("manage_event", _confirmation("rem123"))
    pilot = _pilot(calendar_server=_FakeServer(tool))

    await pilot.set_reminder(None, 1, "2026-08-21T10:00:00", "email the recruiter")

    assert _interviews(db_path) == []


@pytest.mark.asyncio
async def test_a_reminder_for_an_unknown_job_never_reaches_google(db_path):
    tool = _FakeTool("manage_event")
    pilot = _pilot(calendar_server=_FakeServer(tool))

    said = await pilot.set_reminder(None, 999, "2026-08-21T10:00:00", "x")

    assert tool.calls == []
    assert "no job with id 999" in said


@pytest.mark.asyncio
async def test_a_failed_reminder_says_nothing_was_saved(db_path):
    # Unlike an interview, a reminder has no dashboard row to fall back on.
    # Wording that implies a partial save would be a lie.
    tool = _FakeTool("manage_event", RuntimeError("token expired"))
    pilot = _pilot(calendar_server=_FakeServer(tool))

    said = await pilot.set_reminder(None, 1, "2026-08-21T10:00:00", "x")

    assert "not" in said.lower()
    assert "dashboard" not in said.lower()


@pytest.mark.asyncio
async def test_a_failed_reminder_is_logged(db_path, caplog):
    tool = _FakeTool("manage_event", RuntimeError("token expired"))
    pilot = _pilot(calendar_server=_FakeServer(tool))

    with caplog.at_level("ERROR"):
        await pilot.set_reminder(None, 1, "2026-08-21T10:00:00", "x")

    assert "token expired" in caplog.text


@pytest.mark.asyncio
async def test_a_reminder_needs_a_calendar_to_be_configured(db_path):
    pilot = _pilot(calendar_server=None)

    said = await pilot.set_reminder(None, 1, "2026-08-21T10:00:00", "x")

    assert "not" in said.lower()


@pytest.mark.asyncio
async def test_an_unparseable_reminder_time_never_reaches_google(db_path):
    tool = _FakeTool("manage_event")
    pilot = _pilot(calendar_server=_FakeServer(tool))

    said = await pilot.set_reminder(None, 1, "sometime Friday", "x")

    assert tool.calls == []
    assert "not" in said.lower()


@pytest.mark.asyncio
async def test_an_untracked_job_is_refused_before_google_is_called(db_path):
    # record_interview rejects a job with no application. Calling Google first
    # would leave an event on the calendar for an interview nothing recorded.
    conn = connect(db_path)
    conn.execute("INSERT INTO job (source, source_id, title, company, location, "
                 "apply_url) VALUES ('seed','s2','Data Analyst','Zoho','Chennai','u')")
    conn.commit()
    conn.close()
    tool = _FakeTool("manage_event")
    pilot = _pilot(calendar_server=_FakeServer(tool))

    said = await pilot.schedule_interview(None, 2, "2026-08-18T15:00:00")

    assert tool.calls == []
    assert "not tracked" in said.lower()

