import json

from core.jobs import fetch_jobs, query_from_profile
from core.profile import get_profile
from core.scoring import get_matches, score_jobs


def do_fetch_for_profile(conn) -> list[dict]:
    profile = get_profile(conn)
    if profile is None:
        return []
    what, where = query_from_profile(profile)
    return do_search(conn, what, where)


def do_search(conn, query: str, location: str) -> list[dict]:
    jobs = fetch_jobs(conn, query, location)
    if jobs:
        score_jobs(conn, [j["id"] for j in jobs])
    return jobs


def do_explain(conn, job_id: int) -> str:
    job = conn.execute("SELECT * FROM job WHERE id=?", (job_id,)).fetchone()
    if job is None:
        return f"I could not find a job with id {job_id}."
    m = get_matches(conn, [job_id]).get(job_id)
    if m is None:
        return f"{job['title']} at {job['company']} has not been scored yet."
    matched = ", ".join(m["matched_skills"]) or "nothing specific"
    gaps = "; ".join(m["gaps"]) or "no clear gaps"
    return (f"{job['title']} at {job['company']} scores {m['score']}. "
            f"You match on {matched}. Gaps: {gaps}. {m['rationale']}")
