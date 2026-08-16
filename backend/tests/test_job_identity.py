"""The agent must never act on a job id it made up.

In testing the co-pilot was asked to mark a Kotak Mahindra Bank role as
applied. `find_jobs` answered "Found 1. Data Science ... at Kotak Mahindra
Bank." — prose with no identifier in it — and the model then called
`mark_applied(job_id=1)`, reading the count as an id. Job 1 was an unrelated
AI Intern posting, which is what the dashboard then showed as applied while
the agent reported success. Both halves are covered here: lookups have to hand
back ids, and writes have to refuse ids that do not name a job.
"""

import pytest

from core.db import connect, init_db


class _FakeParticipant:
    async def publish_data(self, data, reliable=True):
        pass


class _FakeRoom:
    def __init__(self):
        self.local_participant = _FakeParticipant()

    def on(self, event, callback):
        pass


@pytest.fixture
def pilot(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    seed = connect(str(tmp_path / "t.db"))
    init_db(seed)
    seed.execute("INSERT INTO job (source, source_id, title, company, location, "
                 "apply_url) VALUES ('seed','s1','Backend Engineer',"
                 "'Freshworks','Chennai','u')")
    seed.execute("INSERT INTO job (source, source_id, title, company, location, "
                 "apply_url) VALUES ('seed','s2','Data Scientist',"
                 "'Kotak Mahindra Bank','Mumbai','u')")
    seed.commit()
    seed.close()

    from agent.personas import CoPilot
    return CoPilot(_FakeRoom())


@pytest.mark.asyncio
async def test_find_jobs_hands_back_ids(pilot):
    out = await pilot.find_jobs(None, "Kotak Mahindra Bank")
    assert "#2" in out, f"no id for the model to act on: {out!r}"


@pytest.mark.asyncio
async def test_find_jobs_never_leads_with_a_bare_count(pilot):
    # "Found 1." is the exact wording the model mistook for an id.
    out = await pilot.find_jobs(None, "Kotak Mahindra Bank")
    assert not out.lstrip().lower().startswith("found 1"), out


@pytest.mark.asyncio
async def test_mark_applied_refuses_an_id_that_names_no_job(pilot):
    out = await pilot.mark_applied(None, 999)
    assert "no job" in out.lower()
    assert pilot._db().execute(
        "SELECT COUNT(*) FROM application").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_advance_stage_refuses_an_id_that_names_no_job(pilot):
    out = await pilot.advance_stage(None, 999, "round_1")
    assert "no job" in out.lower()
    assert pilot._db().execute(
        "SELECT COUNT(*) FROM application").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_save_job_refuses_an_id_that_names_no_job(pilot):
    out = await pilot.save_job(None, 999)
    assert "no job" in out.lower()
    assert pilot._db().execute(
        "SELECT COUNT(*) FROM application").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_mark_applied_names_the_job_it_actually_touched(pilot):
    # The model said "I've marked the Kotak role as applied" after writing to a
    # completely different job. If the tool names what it touched, that claim
    # cannot be made without the model contradicting its own tool output.
    out = await pilot.mark_applied(None, 1)
    assert "Backend Engineer" in out and "Freshworks" in out


@pytest.mark.asyncio
async def test_advance_stage_names_the_job_it_actually_touched(pilot):
    out = await pilot.advance_stage(None, 2, "round_1")
    assert "Data Scientist" in out and "Kotak Mahindra Bank" in out
