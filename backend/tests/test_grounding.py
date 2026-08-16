import json
from datetime import datetime

import pytest

from core.db import connect, init_db
from agent import grounding


# ---- today ------------------------------------------------------------
# Without a date the model resolves "Friday at 3" against its training data,
# which books interviews on the wrong Friday -- often one already past.

def test_today_names_the_day_the_user_is_actually_living_in():
    line = grounding.today(datetime(2026, 8, 16, 9, 30))
    assert "Sunday 16 August 2026" in line


def test_today_names_the_zone_relative_times_resolve_against():
    line = grounding.today(datetime(2026, 8, 16, 9, 30))
    assert "Asia/Kolkata" in line


def test_today_tells_the_model_what_to_do_with_it():
    # A bare date gets treated as trivia; the model has to be told it is the
    # anchor for every relative time it is given.
    line = grounding.today(datetime(2026, 8, 16, 9, 30))
    assert "iso" in line.lower()


def test_today_reads_the_real_clock_when_given_nothing():
    assert str(datetime.now().year) in grounding.today()


# ---- the date reaching the model --------------------------------------

class _FakeTurnCtx:
    def __init__(self):
        self.messages = []

    def add_message(self, role, content):
        self.messages.append((role, content))


class _FakeRoom:
    def on(self, event, callback):
        pass


def _pilot(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    from agent.personas import CoPilot
    return CoPilot(_FakeRoom())


@pytest.mark.asyncio
async def test_the_model_is_told_the_date_before_it_answers(tmp_path, monkeypatch):
    pilot = _pilot(tmp_path, monkeypatch)
    turn = _FakeTurnCtx()

    await pilot.on_user_turn_completed(turn, None)

    assert any("Today is" in content for _, content in turn.messages)


@pytest.mark.asyncio
async def test_a_broken_job_feed_does_not_also_cost_the_date(tmp_path, monkeypatch):
    # The feed lookup hits the DB and is allowed to fail without killing the
    # turn. The date needs no DB at all, so it must survive that failure --
    # otherwise a transient feed error silently reintroduces wrong-date
    # bookings.
    pilot = _pilot(tmp_path, monkeypatch)

    def boom(conn):
        raise RuntimeError("db is gone")

    monkeypatch.setattr(grounding, "current_jobs", boom)
    turn = _FakeTurnCtx()

    await pilot.on_user_turn_completed(turn, None)

    assert any("Today is" in content for _, content in turn.messages)


@pytest.mark.asyncio
async def test_an_interviewer_is_not_told_the_date(tmp_path, monkeypatch):
    # Interview mode runs on an emptied context on purpose; the interviewer has
    # no scheduling tools and no business seeing command-center context.
    pilot = _pilot(tmp_path, monkeypatch)
    monkeypatch.setattr(type(pilot), "interviewing", property(lambda self: True))
    from agent.personas import Interview
    pilot._interview = Interview(1, ["Q1"])
    turn = _FakeTurnCtx()

    await pilot.on_user_turn_completed(turn, None)

    assert turn.messages == []


def _conn(tmp_path, n=3, scored=True):
    c = connect(str(tmp_path / "t.db"))
    init_db(c)
    ids = []
    for i in range(n):
        cur = c.execute(
            "INSERT INTO job (source, source_id, title, company, location, "
            "apply_url) VALUES ('seed',?,?,?,'Chennai','u')",
            (f"s{i}", f"Job {i}", f"Co {i}"))
        ids.append(cur.lastrowid)
    if scored:
        for rank, jid in enumerate(ids):
            c.execute(
                """INSERT INTO match (job_id, profile_id, score, matched_skills_json,
                   gaps_json, rationale, scored_at)
                   VALUES (?,1,?,'[]','[]','x','now')""", (jid, 90 - rank))
    c.execute("INSERT INTO fetch_run (query, source, ran_at, job_ids_json) "
              "VALUES ('q','seed','now',?)", (json.dumps(ids),))
    c.commit()
    return c


def test_lists_each_job_with_the_details_needed_to_act_on_it(tmp_path):
    conn = _conn(tmp_path)
    text = grounding.current_jobs(conn)
    assert "#1" in text
    assert "Job 0" in text
    assert "Co 0" in text
    assert "90" in text


def test_untracked_jobs_say_so_rather_than_being_blank(tmp_path):
    conn = _conn(tmp_path)
    assert "not tracked" in grounding.current_jobs(conn)


def test_a_tracked_job_shows_its_stage(tmp_path):
    conn = _conn(tmp_path)
    from core import tracker
    tracker.advance_stage(conn, 1, "screening")
    assert "screening" in grounding.current_jobs(conn)


def test_unscored_jobs_are_marked_not_given_a_fake_score(tmp_path):
    conn = _conn(tmp_path, scored=False)
    text = grounding.current_jobs(conn)
    assert "unscored" in text
    assert "score 0" not in text


def test_highest_scoring_jobs_come_first(tmp_path):
    conn = _conn(tmp_path)
    lines = [ln for ln in grounding.current_jobs(conn).splitlines() if ln.startswith("#")]
    scores = [int(ln.split("score ")[1].split()[0]) for ln in lines]
    assert scores == sorted(scores, reverse=True)


def test_long_feeds_are_capped_and_say_they_were_truncated(tmp_path):
    # Otherwise the agent reads a partial list as the whole world and claims a
    # job doesn't exist when it is merely past the cap.
    conn = _conn(tmp_path, n=30)
    text = grounding.current_jobs(conn)
    assert len([ln for ln in text.splitlines() if ln.startswith("#")]) == 20
    assert "30" in text


def test_an_empty_feed_says_so_instead_of_returning_nothing(tmp_path):
    c = connect(str(tmp_path / "t.db"))
    init_db(c)
    text = grounding.current_jobs(c)
    assert text.strip() != ""
    assert "no jobs" in text.lower()
