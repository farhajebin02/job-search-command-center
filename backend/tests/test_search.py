from core.db import connect, init_db
from core import search, tracker


def _conn(tmp_path):
    c = connect(str(tmp_path / "t.db"))
    init_db(c)
    c.execute("INSERT INTO job (source, source_id, title, company, location, "
              "apply_url) VALUES ('seed','s1','Backend Engineer','Freshworks','Chennai','u')")
    c.execute("INSERT INTO job (source, source_id, title, company, location, "
              "apply_url) VALUES ('seed','s2','Data Analyst','Zoho','Chennai','u')")
    c.commit()
    return c


def test_find_jobs_matches_company_case_insensitively(tmp_path):
    r = search.find_jobs(_conn(tmp_path), "freshworks")
    assert [j["company"] for j in r] == ["Freshworks"]


def test_find_jobs_matches_title_substring(tmp_path):
    r = search.find_jobs(_conn(tmp_path), "analyst")
    assert [j["title"] for j in r] == ["Data Analyst"]


def test_find_jobs_matches_a_stage_name(tmp_path):
    conn = _conn(tmp_path)
    tracker.mark_applied(conn, 1)
    tracker.advance_stage(conn, 1, "round_2")
    r = search.find_jobs(conn, "round 2")
    assert [j["id"] for j in r] == [1]


def test_find_jobs_attaches_stage_when_tracked(tmp_path):
    conn = _conn(tmp_path)
    tracker.mark_applied(conn, 1)
    assert search.find_jobs(conn, "freshworks")[0]["stage"] == "applied"


def test_find_jobs_returns_empty_for_no_match(tmp_path):
    assert search.find_jobs(_conn(tmp_path), "quantum welder") == []
