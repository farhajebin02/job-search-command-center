import pytest
from core.db import connect, init_db
from core.profile import save_profile
from agent import tools


def _conn(tmp_path):
    c = connect(str(tmp_path / "t.db"))
    init_db(c)
    save_profile(c, {"full_name": "T", "email": "", "years_experience": 4,
                     "seniority": "mid", "skills": ["Python"],
                     "titles": ["Backend Engineer"], "locations": ["Chennai"]},
                 raw_text="r")
    return c


def test_do_explain_reports_score_and_gaps(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    cur = conn.execute(
        "INSERT INTO job (source, source_id, title, company, location, apply_url) "
        "VALUES ('seed','s1','Backend Engineer','Freshworks','Chennai','u')")
    jid = cur.lastrowid
    conn.execute(
        """INSERT INTO match (job_id, profile_id, score, matched_skills_json,
             gaps_json, rationale, scored_at)
           VALUES (?,1,82,'["Python"]','["No Kubernetes experience listed"]','Fits.','now')""",
        (jid,))
    conn.commit()

    said = tools.do_explain(conn, jid)
    assert "82" in said
    assert "Python" in said
    assert "Kubernetes" in said


def test_do_explain_is_explicit_when_unscored(tmp_path):
    conn = _conn(tmp_path)
    cur = conn.execute(
        "INSERT INTO job (source, source_id, title, company, location, apply_url) "
        "VALUES ('seed','s2','Dev','Co','Chennai','u')")
    conn.commit()
    assert "not been scored" in tools.do_explain(conn, cur.lastrowid)


def test_do_explain_handles_missing_job(tmp_path):
    assert "could not find" in tools.do_explain(_conn(tmp_path), 9999).lower()


def test_do_search_scores_what_it_fetches(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    monkeypatch.setattr(tools, "fetch_jobs", lambda c, w, l: [
        {"id": 1, "title": "X", "company": "Y", "location": l}])
    called = {}
    monkeypatch.setattr(tools, "score_jobs",
                        lambda c, ids: called.setdefault("ids", ids))
    tools.do_search(conn, "backend", "Chennai")
    assert called["ids"] == [1]
