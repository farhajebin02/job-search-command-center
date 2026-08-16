"""The interview is a mode, not a second agent.

Every earlier version handed off to a separate MockInterviewer by returning it
from a function tool. On the realtime path the SDK drops tool output *and the
handoff* whenever the speech is interrupted -- `agent_activity.py` cancels the
executor and returns, commenting that handoffs "must stay retryable". So
interrupting the interviewer mid-sentence stranded the session inside it, and
the only exits were themselves handoff tools.

Switching modes in Python removes the failure entirely: by the time a speech
can be interrupted, the swap has already happened to local state. These tests
pin that down, plus the isolation the interview needs -- it must not carry the
casual command-center conversation into a professional interview.
"""

import json

import pytest

from core.db import connect, init_db


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


def _names(agent) -> set[str]:
    return {t.info.name for t in agent.tools}


async def _say(agent, role: str, text: str) -> None:
    """Append a turn the way the session would."""
    ctx = agent.chat_ctx.copy()
    ctx.add_message(role=role, content=text)
    await agent.update_chat_ctx(ctx)


@pytest.fixture
def pilot(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    seed = connect(str(tmp_path / "t.db"))
    init_db(seed)
    seed.execute("INSERT INTO job (source, source_id, title, company, location, "
                 "description, apply_url) VALUES ('seed','s1','Backend Engineer',"
                 "'Freshworks','Chennai','Django.','u')")
    seed.commit()
    seed.close()

    from core import mock
    monkeypatch.setattr(mock, "build_questions",
                        lambda conn, job_id: ["Q1", "Q2", "Q3"])

    from agent.personas import CoPilot
    return CoPilot(_FakeRoom())


@pytest.mark.asyncio
async def test_entering_the_interview_swaps_the_instructions(pilot):
    await pilot.enter_interview(1)
    assert "mock job interview" in pilot.instructions.lower()
    assert "Q1" in pilot.instructions


@pytest.mark.asyncio
async def test_entering_the_interview_hides_the_job_tools(pilot):
    # An interviewer that can still search jobs will answer "change my status"
    # with a status change instead of staying in role.
    await pilot.enter_interview(1)
    assert "find_jobs" not in _names(pilot)
    assert "mark_applied" not in _names(pilot)
    assert {"end_mock_interview", "abandon_interview"} <= _names(pilot)


@pytest.mark.asyncio
async def test_the_interview_starts_from_an_empty_context(pilot):
    # A strict interviewer must not remember the casual conversation that
    # preceded it, and counting answers is only correct from a clean slate.
    await _say(pilot, "user", "find me some jobs in Chennai")
    await _say(pilot, "assistant", "Found 20.")

    await pilot.enter_interview(1)

    assert pilot.chat_ctx.messages() == []


@pytest.mark.asyncio
async def test_leaving_the_interview_restores_the_co_pilot(pilot):
    from agent.personas import CO_PILOT_INSTRUCTIONS

    await pilot.enter_interview(1)
    await pilot.leave_interview()

    assert pilot.instructions == CO_PILOT_INSTRUCTIONS
    assert "find_jobs" in _names(pilot)
    assert "end_mock_interview" not in _names(pilot)


@pytest.mark.asyncio
async def test_leaving_the_interview_brings_back_the_earlier_conversation(pilot):
    # Isolation runs one way. The user should not have to re-establish what
    # they were doing before practising.
    await _say(pilot, "user", "find me some jobs in Chennai")

    await pilot.enter_interview(1)
    await _say(pilot, "user", "an answer to Q1")
    await pilot.leave_interview()

    said = [m.text_content for m in pilot.chat_ctx.messages()]
    assert "find me some jobs in Chennai" in said
    assert "an answer to Q1" not in said


@pytest.mark.asyncio
async def test_the_interview_tools_never_return_an_agent(pilot):
    # This is the whole point. A returned Agent is a handoff, and the SDK drops
    # handoffs when the speech is interrupted.
    from livekit.agents import Agent

    await pilot.enter_interview(1)
    out = await pilot.abandon_interview(None)
    assert not isinstance(out, Agent)


@pytest.mark.asyncio
async def test_abandoning_leaves_the_interview_immediately(pilot):
    await pilot.enter_interview(1)
    await pilot.abandon_interview(None)
    assert pilot.interviewing is False
    assert "find_jobs" in _names(pilot)


@pytest.mark.asyncio
async def test_end_mock_interview_refuses_before_every_question_is_answered(pilot):
    await pilot.enter_interview(1)
    await _say(pilot, "user", "only one answer")

    out = await pilot.end_mock_interview(None, ["s"], ["i"])

    assert "not finished" in out.lower()
    assert pilot.interviewing is True


@pytest.mark.asyncio
async def test_end_mock_interview_counts_answers_from_the_isolated_context(pilot):
    # The old counter subtracted a baseline captured from the co-pilot's
    # history. An empty context means the count is simply the answers given.
    await _say(pilot, "user", "chatter before the interview")
    await pilot.enter_interview(1)
    for i in range(3):
        await _say(pilot, "user", f"answer {i}")

    out = await pilot.end_mock_interview(None, ["s1", "s2"], ["i1", "i2"])

    assert "not finished" not in out.lower()
    assert pilot.interviewing is False


@pytest.mark.asyncio
async def test_the_practice_button_enters_the_interview(pilot):
    from core.events import encode

    await pilot.handle_ui_command(
        encode("ui.command", {"command": "start_mock_interview", "job_id": 1}))

    assert pilot.interviewing is True
    assert {"type": "navigate", "payload": {"path": "/practice/1"}} \
        in pilot._room.local_participant.published


@pytest.mark.asyncio
async def test_the_exit_button_leaves_the_interview(pilot):
    from core.events import encode

    await pilot.enter_interview(1)
    await pilot.handle_ui_command(encode("ui.command", {"command": "end_practice"}))

    assert pilot.interviewing is False


@pytest.mark.asyncio
async def test_ui_commands_no_longer_need_a_session(pilot):
    # The old handler resolved `Agent.session`, which raises unless that agent
    # is the running one -- so every command was dropped the moment an
    # interview started. With one agent there is nothing to resolve.
    from core.events import encode

    await pilot.handle_ui_command(
        encode("ui.command", {"command": "start_mock_interview", "job_id": 1}))

    assert pilot.interviewing is True


@pytest.mark.asyncio
async def test_the_context_is_emptied_before_the_tools_change(pilot):
    """Order matters, and getting it wrong killed the Gemini Live session.

    `update_tools` marks the realtime session for restart, and the new session
    is seeded from whatever the plugin currently holds. `update_chat_ctx`
    cannot remove messages on Gemini Live -- it only appends a diff and then
    assumes the result. Emptying after the restart is marked therefore replays
    the full history into the new session and leaves the plugin believing it is
    empty; the reconnect then sent a batch Gemini rejected with 1007
    "Content chunks have multiple roles", unrecoverable.
    """
    calls: list[str] = []

    async def _rec(name, real):
        async def inner(*a, **k):
            calls.append(name)
            return await real(*a, **k)
        return inner

    pilot.update_chat_ctx = await _rec("ctx", pilot.update_chat_ctx)
    pilot.update_tools = await _rec("tools", pilot.update_tools)
    pilot.update_instructions = await _rec("instructions", pilot.update_instructions)

    await pilot.enter_interview(1)

    assert calls.index("ctx") < calls.index("tools"), calls


@pytest.mark.asyncio
async def test_entering_twice_does_not_destroy_the_saved_conversation(pilot):
    # The model called start_mock_interview twice for one request. The second
    # call saved the already-emptied context as the thing to restore, so
    # leaving the interview would have handed back nothing.
    await _say(pilot, "user", "find me some jobs in Chennai")

    await pilot.enter_interview(1)
    await pilot.enter_interview(1)
    await pilot.leave_interview()

    said = [m.text_content for m in pilot.chat_ctx.messages()]
    assert "find me some jobs in Chennai" in said
