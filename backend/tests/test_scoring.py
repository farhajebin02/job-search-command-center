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


def test_prompt_sanitizes_newlines_in_job_fields(tmp_path):
    conn = connect(str(tmp_path / "t.db"))
    init_db(conn)
    save_profile(conn, {"full_name": "T", "email": "", "years_experience": 4,
                        "seniority": "mid", "skills": ["Python"],
                        "titles": ["Backend Engineer"], "locations": ["Chennai"]},
                 raw_text="r")

    # Insert job with multi-line description (paragraphs and bullets like real data)
    desc_with_newlines = (
        "Senior Python Backend role. We need someone with strong skills.\n"
        "Responsibilities:\n"
        "- Build REST APIs\n"
        "- Manage databases\n"
        "- Mentor junior engineers\n"
        "Benefits: Remote, flexible hours."
    )
    cur = conn.execute(
        """INSERT INTO job (source, source_id, title, company, location,
             description, apply_url) VALUES (?,?,?,?,?,?,?)""",
        ("seed", "s0", "Senior Backend Engineer", "TechCorp", "Chennai",
         desc_with_newlines, "u"))
    job_id = cur.lastrowid
    conn.commit()

    jobs = [dict(r) for r in conn.execute("SELECT * FROM job WHERE id=?", (job_id,))]
    p = {"skills": ["Python"], "seniority": "mid", "years_experience": 4,
         "titles": ["Backend Engineer"]}
    prompt = scoring.build_scoring_prompt(p, jobs)

    # Header is: 1 line (score) + 1 line (rules) + 1 empty + 1 CANDIDATE + 1 empty = 5 lines
    # With 1 job and sanitization, prompt should have 5 + 1 = 6 lines total
    # Without sanitization, embedded \n in description creates extra lines
    lines = prompt.splitlines()
    header_lines = 5
    job_count = 1
    expected_lines = header_lines + job_count

    # Assert exactly one line per job starts with "JOB {id} ::"
    job_lines = [ln for ln in lines if ln.startswith("JOB ")]
    assert len(job_lines) == 1, f"Expected 1 job line, got {len(job_lines)}"

    # Assert prompt line count is exactly what we expect (header + jobs, no embedded newlines)
    assert len(lines) == expected_lines, (
        f"Expected {expected_lines} lines (header {header_lines} + jobs {job_count}), "
        f"got {len(lines)}. Newlines in description were not sanitized."
    )

    # Verify description content is present but whitespace-collapsed
    assert "Senior" in job_lines[0] and "Backend" in job_lines[0]
    assert "Python" in prompt
