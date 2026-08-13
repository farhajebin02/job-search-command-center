import json
from core.db import connect, init_db
from core import jobs

RAW = {
    "id": "123", "title": "Backend Engineer",
    "company": {"display_name": "Freshworks"},
    "location": {"display_name": "Chennai, Tamil Nadu"},
    "description": "Python and Django.",
    "salary_min": 1200000, "salary_max": 1800000,
    "redirect_url": "https://adzuna.example/job/123",
    "created": "2026-08-01T00:00:00Z",
}


def _conn(tmp_path):
    c = connect(str(tmp_path / "t.db"))
    init_db(c)
    return c


def test_normalize_maps_nested_adzuna_fields():
    j = jobs.normalize_adzuna(RAW)
    assert j["source"] == "adzuna"
    assert j["source_id"] == "123"
    assert j["company"] == "Freshworks"
    assert j["location"] == "Chennai, Tamil Nadu"
    assert j["apply_url"] == "https://adzuna.example/job/123"


def test_normalize_tolerates_missing_optional_fields():
    j = jobs.normalize_adzuna({"id": "9", "title": "Dev", "redirect_url": "u"})
    assert j["company"] == ""
    assert j["salary_min"] is None


def test_query_from_profile_uses_first_title_and_location():
    what, where = jobs.query_from_profile(
        {"titles": ["Backend Engineer", "SRE"], "locations": ["Chennai"], "skills": []}
    )
    assert what == "Backend Engineer"
    assert where == "Chennai"


def test_query_from_profile_falls_back_to_skills_and_india():
    what, where = jobs.query_from_profile(
        {"titles": [], "locations": [], "skills": ["Python", "React"]}
    )
    assert what == "Python"
    assert where == "India"


def test_fetch_jobs_falls_back_to_seed_when_source_fails(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    monkeypatch.setattr(jobs, "fetch_adzuna",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    saved = jobs.fetch_jobs(conn, "backend", "Chennai")
    assert len(saved) > 0
    assert all(j["source"] == "seed" for j in saved)


def test_fetch_jobs_upserts_rather_than_duplicating(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    monkeypatch.setattr(jobs, "fetch_adzuna", lambda *a, **k: [jobs.normalize_adzuna(RAW)])
    jobs.fetch_jobs(conn, "backend", "Chennai")
    jobs.fetch_jobs(conn, "backend", "Chennai")
    assert conn.execute("SELECT COUNT(*) FROM job").fetchone()[0] == 1


def test_fetch_jobs_records_a_fetch_run(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    monkeypatch.setattr(jobs, "fetch_adzuna", lambda *a, **k: [jobs.normalize_adzuna(RAW)])
    jobs.fetch_jobs(conn, "backend", "Chennai")
    row = conn.execute("SELECT * FROM fetch_run ORDER BY id DESC LIMIT 1").fetchone()
    assert row["query"] == "backend | Chennai"
    assert len(json.loads(row["job_ids_json"])) == 1


def test_last_fetch_returns_jobs_from_most_recent_run(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    monkeypatch.setattr(jobs, "fetch_adzuna", lambda *a, **k: [jobs.normalize_adzuna(RAW)])
    jobs.fetch_jobs(conn, "backend", "Chennai")
    assert [j["source_id"] for j in jobs.last_fetch(conn)] == ["123"]


def test_last_fetch_is_empty_on_cold_db(tmp_path):
    assert jobs.last_fetch(_conn(tmp_path)) == []
