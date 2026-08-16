import json

import pytest

from core.db import connect, init_db
from core.events import encode


class _FakeParticipant:
    def __init__(self):
        self.published = []

    async def publish_data(self, data, reliable=True):
        self.published.append(json.loads(data.decode()))


class _FakeRoom:
    def __init__(self):
        self.local_participant = _FakeParticipant()
        self.handlers = {}

    def on(self, event, callback):
        self.handlers[event] = callback


class _FakeSession:
    """Stands in for AgentSession, whose update_agent() performs the handoff."""

    def __init__(self):
        self.agents = []

    def update_agent(self, agent):
        self.agents.append(agent)


@pytest.fixture
def pilot(tmp_path, monkeypatch):
    """A CoPilot wired to a throwaway DB, a fake room, and a fake session."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    seed = connect(str(tmp_path / "t.db"))
    init_db(seed)
    seed.execute("INSERT INTO job (source, source_id, title, company, location, "
                 "description, apply_url) VALUES ('seed','s1','Backend Engineer',"
                 "'Freshworks','Chennai','Django.','u')")
    seed.commit()
    seed.close()

    from core import mock
    monkeypatch.setattr(mock, "build_questions", lambda conn, job_id: ["Q1", "Q2", "Q3"])

    from agent.personas import CoPilot

    room = _FakeRoom()
    agent = CoPilot(room)
    session = _FakeSession()
    monkeypatch.setattr(type(agent), "session", property(lambda self: session))
    return agent, room, session


@pytest.mark.asyncio
async def test_ui_command_switches_into_interview_mode(pilot):
    # The Practice button must reach the same mode switch as the voice command,
    # otherwise the practice screen renders with the co-pilot still driving.
    agent, room, session = pilot

    await agent.handle_ui_command(
        encode("ui.command", {"command": "start_mock_interview", "job_id": 1}))

    assert agent.interviewing is True


@pytest.mark.asyncio
async def test_ui_command_navigates_the_browser_to_the_practice_route(pilot):
    agent, room, session = pilot

    await agent.handle_ui_command(
        encode("ui.command", {"command": "start_mock_interview", "job_id": 1}))

    published = room.local_participant.published
    assert {"type": "navigate", "payload": {"path": "/practice/1"}} in published


@pytest.mark.asyncio
async def test_commands_work_without_any_session_at_all(tmp_path, monkeypatch):
    # `Agent.session` raises unless that agent is the running one, so the old
    # design dropped every UI command the moment an interview started --
    # including the one whose whole job was ending it. A mode switch touches
    # local state only, so there is no session to resolve.
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    seed = connect(str(tmp_path / "t.db"))
    init_db(seed)
    seed.close()

    from core import mock
    monkeypatch.setattr(mock, "build_questions", lambda conn, job_id: ["Q1"])

    from agent.personas import CoPilot

    agent = CoPilot(_FakeRoom())

    # Exactly what the SDK does when this agent is not the active one.
    def _raises(self):
        raise RuntimeError("no activity context found, the agent is not running")
    monkeypatch.setattr(type(agent), "session", property(_raises))

    await agent.handle_ui_command(
        encode("ui.command", {"command": "start_mock_interview", "job_id": 1}))
    assert agent.interviewing is True

    await agent.handle_ui_command(encode("ui.command", {"command": "end_practice"}))
    assert agent.interviewing is False


@pytest.mark.asyncio
async def test_leaving_the_practice_screen_restores_the_co_pilot(pilot):
    # The Exit link only navigated the browser. The session stayed an
    # interviewer, so the next request got an interview question back.
    agent, room, session = pilot
    await agent.enter_interview(1)

    await agent.handle_ui_command(encode("ui.command", {"command": "end_practice"}))

    assert agent.interviewing is False


@pytest.mark.asyncio
async def test_unknown_ui_command_is_ignored(pilot):
    agent, room, session = pilot

    await agent.handle_ui_command(
        encode("ui.command", {"command": "launch_the_missiles", "job_id": 1}))

    assert agent.interviewing is False
    assert room.local_participant.published == []


@pytest.mark.asyncio
async def test_the_agents_own_outbound_events_are_ignored(pilot):
    # The agent publishes on the same data channel it now listens to, so its
    # own events must not be mistaken for commands.
    agent, room, session = pilot

    await agent.handle_ui_command(encode("jobs.updated", {"count": 3}))

    assert agent.interviewing is False


@pytest.mark.asyncio
async def test_a_command_before_the_session_starts_still_takes_effect(
        tmp_path, monkeypatch):
    # The listener is registered in __init__ on an already-connected room,
    # before any session exists. That window used to drop the click entirely;
    # a mode switch has no such dependency, so the click now lands and the
    # browser is sent to a practice screen the agent is genuinely ready for.
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    seed = connect(str(tmp_path / "t.db"))
    init_db(seed)
    seed.close()

    from core import mock
    monkeypatch.setattr(mock, "build_questions", lambda conn, job_id: ["Q1"])

    from agent.personas import CoPilot

    room = _FakeRoom()
    agent = CoPilot(room)  # never started

    await agent.handle_ui_command(
        encode("ui.command", {"command": "start_mock_interview", "job_id": 1}))

    assert agent.interviewing is True


@pytest.mark.asyncio
async def test_a_failing_interview_build_is_logged_not_swallowed(pilot, caplog):
    # The listener fires this as a bare create_task, so anything raised here
    # vanishes into an unretrieved task and the Practice click just does
    # nothing. The failure has to reach the log instead.
    agent, room, session = pilot
    from core import mock

    def boom(conn, job_id):
        raise RuntimeError("gemini is down")

    monkey = pytest.MonkeyPatch()
    monkey.setattr(mock, "build_questions", boom)
    try:
        with caplog.at_level("ERROR"):
            await agent.handle_ui_command(
                encode("ui.command", {"command": "start_mock_interview", "job_id": 1}))
    finally:
        monkey.undo()

    assert "gemini is down" in caplog.text
    # And the browser must not be sent to a practice screen for an interview
    # that was never built.
    assert agent.interviewing is False
    assert room.local_participant.published == []


@pytest.mark.asyncio
async def test_malformed_payload_does_not_raise(pilot):
    agent, room, session = pilot

    await agent.handle_ui_command(b"not json at all")

    assert agent.interviewing is False
