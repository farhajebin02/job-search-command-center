from core.db import connect, init_db
from core.profile import save_profile
from core import scoring


def _setup(tmp_path):
    conn = connect(str(tmp_path / "t.db"))
    init_db(conn)
    save_profile(conn, {"full_name": "T", "email": "", "years_experience": 4,
                        "seniority": "mid", "skills": ["Python"],
                        "titles": ["Backend Engineer"], "locations": ["Chennai"]},
                 raw_text="r")
    ids = []
    for i in range(12):
        cur = conn.execute(
            """INSERT INTO job (source, source_id, title, company, location,
                 description, apply_url) VALUES (?,?,?,?,?,?,?)""",
            ("seed", f"s{i}", f"Job {i}", "Co", "Chennai", "Python work", "u"))
        ids.append(cur.lastrowid)
    conn.commit()
    return conn, ids


def test_prompt_includes_profile_skills_and_every_job(tmp_path):
    conn, ids = _setup(tmp_path)
    jobs = [dict(r) for r in conn.execute("SELECT * FROM job LIMIT 2")]
    p = {"skills": ["Python"], "seniority": "mid", "years_experience": 4,
         "titles": ["Backend Engineer"]}
    prompt = scoring.build_scoring_prompt(p, jobs)
    assert "Python" in prompt
    assert str(jobs[0]["id"]) in prompt and str(jobs[1]["id"]) in prompt


def test_score_jobs_batches_in_tens(tmp_path, monkeypatch):
    conn, ids = _setup(tmp_path)
    calls = []

    def fake(prompt, schema, model=None):
        batch = [ln for ln in prompt.splitlines() if ln.startswith("JOB ")]
        calls.append(len(batch))
        return {"results": [{"job_id": ln.split()[1], "score": 70,
                             "matched_skills": ["Python"], "gaps": ["No Kubernetes"],
                             "rationale": "Fits."} for ln in batch]}

    monkeypatch.setattr(scoring, "generate_json", fake)
    scoring.score_jobs(conn, ids)
    assert calls == [10, 2]


def test_score_jobs_writes_match_rows(tmp_path, monkeypatch):
    conn, ids = _setup(tmp_path)
    monkeypatch.setattr(scoring, "generate_json", lambda p, s, m=None: {
        "results": [{"job_id": str(i), "score": 81, "matched_skills": ["Python"],
                     "gaps": ["No Kubernetes"], "rationale": "Good."} for i in ids[:10]]})
    scoring.score_jobs(conn, ids[:10])
    row = conn.execute("SELECT * FROM match WHERE job_id=?", (ids[0],)).fetchone()
    assert row["score"] == 81
    assert row["rationale"] == "Good."


def test_score_jobs_is_idempotent_per_job(tmp_path, monkeypatch):
    conn, ids = _setup(tmp_path)
    monkeypatch.setattr(scoring, "generate_json", lambda p, s, m=None: {
        "results": [{"job_id": str(ids[0]), "score": 55, "matched_skills": [],
                     "gaps": [], "rationale": "x"}]})
    scoring.score_jobs(conn, [ids[0]])
    scoring.score_jobs(conn, [ids[0]])
    assert conn.execute("SELECT COUNT(*) FROM match").fetchone()[0] == 1


def test_get_matches_decodes_json_columns(tmp_path, monkeypatch):
    conn, ids = _setup(tmp_path)
    monkeypatch.setattr(scoring, "generate_json", lambda p, s, m=None: {
        "results": [{"job_id": str(ids[0]), "score": 90,
                     "matched_skills": ["Python"], "gaps": ["No K8s"],
                     "rationale": "y"}]})
    scoring.score_jobs(conn, [ids[0]])
    m = scoring.get_matches(conn, [ids[0]])
    assert m[ids[0]]["matched_skills"] == ["Python"]
    assert m[ids[0]]["gaps"] == ["No K8s"]
