import pytest

from core.db import connect, init_db
from core import mock


def _conn(tmp_path):
    c = connect(str(tmp_path / "t.db"))
    init_db(c)
    c.execute("INSERT INTO job (source, source_id, title, company, location, "
              "description, apply_url) VALUES ('seed','s1','Backend Engineer',"
              "'Freshworks','Chennai','Django, PostgreSQL, Kubernetes.','u')")
    c.execute("""INSERT INTO match (job_id, profile_id, score, matched_skills_json,
                 gaps_json, rationale, scored_at)
                 VALUES (1,1,70,'["Python"]','["No Kubernetes experience listed"]','x','now')""")
    c.commit()
    return c


def test_build_questions_returns_three(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    monkeypatch.setattr(mock, "generate_json", lambda p, s, m=None: {
        "questions": ["Q1", "Q2", "Q3"]})
    assert mock.build_questions(conn, 1) == ["Q1", "Q2", "Q3"]


def test_build_questions_prompt_includes_the_gap(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    seen = {}
    monkeypatch.setattr(mock, "generate_json",
                        lambda p, s, m=None: seen.setdefault("p", p) or {"questions": ["a"]})
    mock.build_questions(conn, 1)
    assert "Kubernetes" in seen["p"]


def _seed_profile(conn):
    from core.profile import save_profile
    save_profile(conn, {
        "full_name": "F J", "email": "f@example.com", "years_experience": 0,
        "seniority": "junior", "skills": ["Python", "Kubernetes"],
        "titles": ["AI Engineer"], "locations": ["Chennai"],
    }, raw_text="resume text")


def test_build_questions_prompt_includes_the_candidates_own_skills(tmp_path, monkeypatch):
    # Questions built from the job alone can't probe the distance between this
    # candidate and this role, which is the whole point of practising.
    conn = _conn(tmp_path)
    _seed_profile(conn)
    seen = {}
    monkeypatch.setattr(mock, "generate_json",
                        lambda p, s, m=None: seen.setdefault("p", p) or {"questions": ["a"]})
    mock.build_questions(conn, 1)
    assert "Python" in seen["p"]
    assert "junior" in seen["p"]


def test_build_questions_works_when_no_resume_is_stored(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    seen = {}
    monkeypatch.setattr(mock, "generate_json",
                        lambda p, s, m=None: seen.setdefault("p", p) or {
                            "questions": ["a", "b", "c"]})
    assert len(mock.build_questions(conn, 1)) == 3
    # No empty résumé section dangling in the prompt.
    assert "CANDIDATE BACKGROUND:" not in seen["p"]


def test_build_questions_falls_back_to_template_on_failure(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    monkeypatch.setattr(mock, "generate_json",
                        lambda p, s, m=None: (_ for _ in ()).throw(RuntimeError("down")))
    qs = mock.build_questions(conn, 1)
    assert len(qs) == 3
    assert any("Backend Engineer" in q for q in qs)


def _ctx(turns):
    from livekit.agents import llm
    ctx = llm.ChatContext.empty()
    for role, text in turns:
        ctx.add_message(role=role, content=text)
    return ctx


def test_format_transcript_labels_each_speaker():
    out = mock.format_transcript(_ctx([
        ("assistant", "Tell me about a hard bug."),
        ("user", "I once chased a race condition for two days."),
    ]))
    assert out == (
        "Interviewer: Tell me about a hard bug.\n"
        "Candidate: I once chased a race condition for two days."
    )


def test_format_transcript_omits_the_system_prompt():
    # The interviewer's instructions are in the context too, and leaking the
    # question list into a saved transcript would be nonsense to read back.
    out = mock.format_transcript(_ctx([
        ("system", "You are conducting a mock job interview."),
        ("user", "Ready when you are."),
    ]))
    assert out == "Candidate: Ready when you are."


def test_format_transcript_skips_empty_turns():
    out = mock.format_transcript(_ctx([
        ("assistant", "   "),
        ("user", "Hello"),
    ]))
    assert out == "Candidate: Hello"


def test_format_transcript_of_an_empty_conversation_is_empty():
    assert mock.format_transcript(_ctx([])) == ""


def test_save_session_persists_transcript_and_feedback(tmp_path):
    conn = _conn(tmp_path)
    sid = mock.save_session(conn, 1, "hello", {"strengths": ["clear"]})
    row = conn.execute("SELECT * FROM mock_session WHERE id=?", (sid,)).fetchone()
    assert row["transcript"] == "hello"
    assert "clear" in row["feedback_json"]


class _FakeParticipant:
    def __init__(self):
        self.published = []

    async def publish_data(self, data, reliable=True):
        self.published.append(data)


class _FakeRoom:
    def __init__(self):
        self.local_participant = _FakeParticipant()
        self.handlers = {}

    def on(self, event, callback):
        # CoPilot subscribes to the data channel in __init__.
        self.handlers[event] = callback


async def _interviewing(tmp_path, monkeypatch, questions=("Q1", "Q2", "Q3")):
    """A co-pilot already switched into interview mode for job 1."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    seed = connect(str(tmp_path / "t.db"))
    init_db(seed)
    seed.close()

    monkeypatch.setattr(mock, "build_questions",
                        lambda conn, job_id: list(questions))

    from agent.personas import CoPilot

    room = _FakeRoom()
    pilot = CoPilot(room)
    await pilot.enter_interview(1)
    return pilot, room


async def _answer(pilot, count):
    """Put `count` candidate answers into the interview's own context."""
    ctx = pilot.chat_ctx.copy()
    for i in range(count):
        ctx.add_message(role="user", content=f"answer {i}")
    await pilot.update_chat_ctx(ctx)


@pytest.mark.asyncio
async def test_end_mock_interview_persists_a_mock_session(tmp_path, monkeypatch):
    # Exercise the actual tool method rather than save_session directly, so the
    # real conversational flow is what proves feedback gets persisted.
    pilot, room = await _interviewing(tmp_path, monkeypatch)
    await _answer(pilot, 3)

    result = await pilot.end_mock_interview(
        None,
        strengths=["clear communication", "solid fundamentals"],
        improvements=["give more specifics", "slow down"],
    )

    assert "complete" in result.lower()
    row = pilot._db().execute(
        "SELECT * FROM mock_session WHERE job_id=1").fetchone()
    assert row is not None
    assert "Candidate: answer 0" in row["transcript"]
    assert "clear communication" in row["feedback_json"]
    assert "give more specifics" in row["feedback_json"]


@pytest.mark.asyncio
async def test_ending_an_interview_returns_to_the_co_pilot(tmp_path, monkeypatch):
    # Without this the session stays an interviewer forever, and every later
    # turn is answered by a mode that has no job tools at all.
    pilot, _ = await _interviewing(tmp_path, monkeypatch)
    await _answer(pilot, 3)

    await pilot.end_mock_interview(None, strengths=["clear"],
                                   improvements=["specifics"])

    assert pilot.interviewing is False


@pytest.mark.asyncio
async def test_a_failed_save_still_returns_to_the_co_pilot(tmp_path, monkeypatch):
    # One bad save must not strand the user in the interview — that is the
    # exact state that made the assistant claim it could not change statuses.
    pilot, _ = await _interviewing(tmp_path, monkeypatch)
    await _answer(pilot, 3)

    monkeypatch.setattr(mock, "save_session", lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("disk is gone")))

    await pilot.end_mock_interview(None, strengths=["clear"],
                                   improvements=["specifics"])

    assert pilot.interviewing is False


@pytest.mark.asyncio
async def test_the_candidate_can_always_walk_out(tmp_path, monkeypatch):
    # end_mock_interview is guarded, and it was once the only way out. That
    # made the interview something a user could enter but never leave.
    pilot, _ = await _interviewing(tmp_path, monkeypatch)

    await pilot.abandon_interview(None)

    assert pilot.interviewing is False


@pytest.mark.asyncio
async def test_walking_out_saves_nothing(tmp_path, monkeypatch):
    # An abandoned interview is not a result worth keeping.
    pilot, _ = await _interviewing(tmp_path, monkeypatch)

    await pilot.abandon_interview(None)

    assert pilot._db().execute(
        "SELECT COUNT(*) FROM mock_session").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_the_refusal_tells_the_model_how_to_get_out(tmp_path, monkeypatch):
    # Without this the model only knows to ask the next question, so it loops
    # forever against a user who wants to do something else.
    pilot, _ = await _interviewing(tmp_path, monkeypatch)

    result = await pilot.end_mock_interview(None, strengths=["clear"],
                                            improvements=["specifics"])

    assert "abandon_interview" in result


@pytest.mark.asyncio
async def test_an_interview_cannot_end_before_it_happens(tmp_path, monkeypatch):
    # The model ended one immediately in live testing. Instructions are a
    # request; this has to be a rule.
    pilot, _ = await _interviewing(tmp_path, monkeypatch)

    result = await pilot.end_mock_interview(None, strengths=["clear"],
                                            improvements=["specifics"])

    assert isinstance(result, str)
    assert pilot.interviewing is True
    assert pilot._db().execute(
        "SELECT COUNT(*) FROM mock_session").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_end_mock_interview_persists_what_was_actually_said(tmp_path, monkeypatch):
    # The saved transcript is the point of keeping a session at all — a blank
    # one makes the record useless to review later.
    pilot, _ = await _interviewing(tmp_path, monkeypatch,
                                   questions=("Tell me about a hard bug.",))
    ctx = pilot.chat_ctx.copy()
    ctx.add_message(role="system", content="You are conducting a mock job interview.")
    ctx.add_message(role="assistant", content="Tell me about a hard bug.")
    ctx.add_message(role="user", content="I chased a race condition for two days.")
    await pilot.update_chat_ctx(ctx)

    await pilot.end_mock_interview(None, strengths=["clear"],
                                   improvements=["more specifics"])

    row = pilot._db().execute(
        "SELECT * FROM mock_session WHERE job_id=1").fetchone()
    assert "Interviewer: Tell me about a hard bug." in row["transcript"]
    assert "Candidate: I chased a race condition for two days." in row["transcript"]
    assert "mock job interview" not in row["transcript"]
