import base64

import pytest

from agent import calendar


class _Job(dict):
    """Stands in for the sqlite3.Row that `CoPilot._job` returns."""


def _job(job_id=1, title="Backend Engineer", company="Freshworks"):
    return _Job(id=job_id, title=title, company=company)


def _link(event_id: str, calendar_id: str = "farhajebin02@gmail.com") -> str:
    """A Google event link the way manage_event hands one back: the id and the
    calendar packed into a base64url `eid`."""
    eid = base64.urlsafe_b64encode(
        f"{event_id} {calendar_id}".encode()).decode().rstrip("=")
    return f"https://www.google.com/calendar/event?eid={eid}"


# ---- build_event ------------------------------------------------------

def test_build_event_titles_the_event_with_the_role_and_company():
    ev = calendar.build_event(_job(), "2026-08-18T15:00:00", "round_1")
    assert ev["summary"] == "Interview: Backend Engineer at Freshworks"


def test_build_event_asks_google_to_create():
    ev = calendar.build_event(_job(), "2026-08-18T15:00:00", "round_1")
    assert ev["action"] == "create"


def test_build_event_pins_a_naive_time_to_the_india_offset():
    # The model hands over a bare ISO string. Sent as-is, Google reads it in
    # whatever the calendar's default zone is and the interview lands at the
    # wrong hour.
    ev = calendar.build_event(_job(), "2026-08-18T15:00:00", "round_1")
    assert ev["start_time"] == "2026-08-18T15:00:00+05:30"


def test_build_event_keeps_a_time_that_already_carries_a_zone():
    ev = calendar.build_event(_job(), "2026-08-18T15:00:00+00:00", "round_1")
    assert ev["start_time"] == "2026-08-18T15:00:00+00:00"


def test_build_event_defaults_to_a_forty_five_minute_slot():
    ev = calendar.build_event(_job(), "2026-08-18T15:00:00", "round_1")
    assert ev["end_time"] == "2026-08-18T15:45:00+05:30"


def test_build_event_names_the_zone_for_google():
    ev = calendar.build_event(_job(), "2026-08-18T15:00:00", "round_1")
    assert ev["timezone"] == "Asia/Kolkata"


def test_build_event_says_which_round_in_the_description():
    ev = calendar.build_event(_job(), "2026-08-18T15:00:00", "round_1")
    assert "round 1" in ev["description"].lower()


def test_build_event_rejects_a_time_it_cannot_parse():
    # Better to skip the calendar than to book "next Tuesday" as a literal.
    assert calendar.build_event(_job(), "next Tuesday", "round_1") is None


# ---- build_reminder ---------------------------------------------------

def test_build_reminder_titles_the_event_as_a_follow_up():
    ev = calendar.build_reminder(_job(), "2026-08-21T10:00:00", "email the recruiter")
    assert ev["summary"] == "Follow up: Backend Engineer at Freshworks"


def test_build_reminder_carries_what_to_do_in_the_description():
    ev = calendar.build_reminder(_job(), "2026-08-21T10:00:00", "email the recruiter")
    assert "email the recruiter" in ev["description"]


def test_build_reminder_pops_up_at_the_moment_it_is_due():
    # A follow-up nudge is useless ten minutes early or an hour late, and a
    # custom override is what stops Google applying the calendar's defaults.
    ev = calendar.build_reminder(_job(), "2026-08-21T10:00:00", "email the recruiter")
    assert ev["reminders"] == [{"method": "popup", "minutes": 0}]


def test_build_reminder_books_a_short_slot_not_a_meeting():
    ev = calendar.build_reminder(_job(), "2026-08-21T10:00:00", "email the recruiter")
    assert ev["start_time"] == "2026-08-21T10:00:00+05:30"
    assert ev["end_time"] == "2026-08-21T10:15:00+05:30"


def test_build_reminder_pins_a_naive_time_to_the_india_offset():
    ev = calendar.build_reminder(_job(), "2026-08-21T10:00:00", "x")
    assert ev["start_time"].endswith("+05:30")


def test_build_reminder_rejects_a_time_it_cannot_parse():
    assert calendar.build_reminder(_job(), "sometime Friday", "x") is None


# ---- parse_event_id ---------------------------------------------------

def test_parse_event_id_decodes_the_id_out_of_the_confirmation_link():
    # manage_event returns prose, not JSON: the id is only recoverable from the
    # base64 `eid` in the link it quotes.
    response = ("Successfully created event 'Interview: Backend Engineer at "
                f"Freshworks' for farhajebin02@gmail.com. Link: {_link('abc123def')}")
    assert calendar.parse_event_id(response) == "abc123def"


def test_parse_event_id_returns_none_when_there_is_no_link():
    assert calendar.parse_event_id("Successfully created event 'x'.") is None


def test_parse_event_id_returns_none_when_the_eid_is_not_decodable():
    response = "Link: https://www.google.com/calendar/event?eid=!!!not-base64!!!"
    assert calendar.parse_event_id(response) is None


def test_parse_event_id_survives_an_empty_response():
    assert calendar.parse_event_id("") is None


# ---- the real thing ---------------------------------------------------
# Captured verbatim from manage_event against a live Google account. The
# earlier fixtures were hand-written plain text and passed while production
# failed: the SDK hands back content[0].model_dump_json(), so the prose is
# wrapped in a JSON envelope and the link is followed immediately by a quote
# rather than whitespace.

LIVE_RESPONSE = (
    '{"type":"text","text":"Successfully created event \'Interview: SMOKE TEST'
    " - safe to delete at Job Command Center' for farhajebin02@gmail.com."
    " Link: https://www.google.com/calendar/event?eid=M3NwYmd2MmIybmNsYjFkMjly"
    'djIyYjdjZHMgZmFyaGFqZWJpbjAyQG0","annotations":null,"meta":null}'
)
LIVE_EVENT_ID = "3spbgv2b2nclb1d29rv22b7cds"


def test_parse_event_id_reads_a_real_manage_event_response():
    assert calendar.parse_event_id(LIVE_RESPONSE) == LIVE_EVENT_ID


def test_parse_event_link_stops_at_the_end_of_the_url():
    link = calendar.parse_event_link(LIVE_RESPONSE)
    assert link is not None
    assert '"' not in link
    assert "annotations" not in link
    assert link.endswith("QG0")


def test_parse_event_id_ignores_a_truncated_calendar_half():
    # Google truncates the calendar id inside the eid -- it decodes to
    # "<event id> farhajebin02@m". The event id half is what matters and is
    # intact, so a parser that insists on a whole email would throw away a
    # perfectly good id.
    import base64
    eid = base64.urlsafe_b64encode(b"evt999 someone@m").decode().rstrip("=")
    response = f"Link: https://www.google.com/calendar/event?eid={eid}"
    assert calendar.parse_event_id(response) == "evt999"


# ---- parse_event_link -------------------------------------------------

def test_parse_event_link_returns_the_url_the_user_can_click():
    link = _link("abc123def")
    assert calendar.parse_event_link(f"Created. Link: {link}") == link


def test_parse_event_link_returns_none_when_absent():
    assert calendar.parse_event_link("Created.") is None


# ---- create_event -----------------------------------------------------

class _FakeToolInfo:
    def __init__(self, name):
        self.name = name


class _FakeTool:
    """Shaped like the FunctionTool that MCPServer.list_tools() hands back:
    named via `.info.name`, invoked with the raw argument dict."""

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
    def __init__(self, *tools):
        self._tools = list(tools)

    async def list_tools(self):
        return self._tools


@pytest.mark.asyncio
async def test_create_event_calls_manage_event_with_the_event_arguments():
    tool = _FakeTool("manage_event")
    server = _FakeServer(_FakeTool("list_calendars"), tool)
    event = calendar.build_event(_job(), "2026-08-18T15:00:00", "round_1")

    await calendar.create_event(server, event)

    assert tool.calls == [event]


@pytest.mark.asyncio
async def test_create_event_returns_the_confirmation_text():
    confirmation = f"Successfully created event 'x'. Link: {_link('abc123def')}"
    server = _FakeServer(_FakeTool("manage_event", confirmation))

    result = await calendar.create_event(
        server, calendar.build_event(_job(), "2026-08-18T15:00:00", "round_1"))

    assert result == confirmation


@pytest.mark.asyncio
async def test_create_event_raises_when_the_server_offers_no_event_tool():
    # A workspace-mcp started without --tools calendar comes up fine and simply
    # has no manage_event. Failing loudly here is what lets schedule_interview
    # tell the user the calendar half did not happen.
    server = _FakeServer(_FakeTool("list_calendars"))

    with pytest.raises(LookupError, match="manage_event"):
        await calendar.create_event(
            server, calendar.build_event(_job(), "2026-08-18T15:00:00", "round_1"))
