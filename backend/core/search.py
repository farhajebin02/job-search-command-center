from core.scoring import get_matches
from core.tracker import STAGES


def find_jobs(conn, query: str) -> list[dict]:
    q = (query or "").strip().lower()
    if not q:
        return []

    stage = next((s for s in STAGES if s.replace("_", " ") == q or s == q), None)
    if stage:
        rows = conn.execute(
            """SELECT j.*, a.stage FROM job j
               JOIN application a ON a.job_id = j.id WHERE a.stage=?""", (stage,))
    else:
        like = f"%{q}%"
        rows = conn.execute(
            """SELECT j.*, a.stage FROM job j
               LEFT JOIN application a ON a.job_id = j.id
               WHERE LOWER(j.company) LIKE ? OR LOWER(j.title) LIKE ?""",
            (like, like))

    jobs = [dict(r) for r in rows]
    matches = get_matches(conn, [j["id"] for j in jobs])
    return [{**j, "match": matches.get(j["id"])} for j in jobs]
