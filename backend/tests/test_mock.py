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


def test_build_questions_falls_back_to_template_on_failure(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    monkeypatch.setattr(mock, "generate_json",
                        lambda p, s, m=None: (_ for _ in ()).throw(RuntimeError("down")))
    qs = mock.build_questions(conn, 1)
    assert len(qs) == 3
    assert any("Backend Engineer" in q for q in qs)


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


@pytest.mark.asyncio
async def test_end_mock_interview_tool_persists_a_mock_session(tmp_path, monkeypatch):
    # MockInterviewer._conn = connect() with no args, so it reads DB_PATH from
    # the environment — exercise the actual tool method (not save_session
    # directly) to prove the real conversational flow now persists feedback.
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    seed = connect(str(tmp_path / "t.db"))
    init_db(seed)
    seed.close()

    from agent.personas import MockInterviewer

    room = _FakeRoom()
    interviewer = MockInterviewer(room, 1, ["Q1", "Q2", "Q3"])

    result = await interviewer.end_mock_interview(
        None,
        strengths=["clear communication", "solid fundamentals"],
        improvements=["give more specifics", "slow down"],
    )

    assert result == "Interview complete."
    row = interviewer._conn.execute(
        "SELECT * FROM mock_session WHERE job_id=1"
    ).fetchone()
    assert row is not None
    assert row["transcript"] == ""
    assert "clear communication" in row["feedback_json"]
    assert "give more specifics" in row["feedback_json"]
    # end_mock_interview should still publish the navigate-home event
    assert len(room.local_participant.published) == 1
