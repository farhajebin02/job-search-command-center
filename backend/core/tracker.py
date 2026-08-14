from datetime import datetime, timezone

STAGES = ["saved", "applied", "screening", "round_1", "round_2",
          "final", "offer", "rejected"]
INTERVIEWING = ["screening", "round_1", "round_2", "final"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get(conn, job_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM application WHERE job_id=?", (job_id,)).fetchone()
    return dict(row) if row else None


def _upsert(conn, job_id: int, stage: str, applied: bool) -> dict:
    existing = _get(conn, job_id)
    if existing is None:
        conn.execute(
            """INSERT INTO application (job_id, stage, applied_at, updated_at, notes)
               VALUES (?,?,?,?,'')""",
            (job_id, stage, _now() if applied else None, _now()))
    else:
        conn.execute(
            """UPDATE application SET stage=?, updated_at=?,
                 applied_at=COALESCE(applied_at, ?) WHERE job_id=?""",
            (stage, _now(), _now() if applied else None, job_id))
    conn.commit()
    return _get(conn, job_id)


def save_job(conn, job_id: int) -> dict:
    return _upsert(conn, job_id, "saved", applied=False)


def mark_applied(conn, job_id: int) -> dict:
    return _upsert(conn, job_id, "applied", applied=True)


def advance_stage(conn, job_id: int, stage: str) -> dict:
    if stage not in STAGES:
        raise ValueError(f"Unknown stage: {stage}")
    if _get(conn, job_id) is None:
        raise ValueError(f"Job {job_id} is not tracked yet")
    conn.execute("UPDATE application SET stage=?, updated_at=? WHERE job_id=?",
                 (stage, _now(), job_id))
    conn.commit()
    return _get(conn, job_id)


def list_applications(conn, stage: str | None = None) -> list[dict]:
    sql = ("SELECT a.*, j.title, j.company, j.apply_url FROM application a "
           "JOIN job j ON j.id = a.job_id")
    if stage == "interviewing":
        sql += f" WHERE a.stage IN ({','.join('?' * len(INTERVIEWING))})"
        return [dict(r) for r in conn.execute(sql, INTERVIEWING)]
    if stage:
        return [dict(r) for r in conn.execute(sql + " WHERE a.stage=?", (stage,))]
    return [dict(r) for r in conn.execute(sql)]


def pipeline_summary(conn) -> str:
    rows = conn.execute(
        "SELECT stage, COUNT(*) c FROM application GROUP BY stage").fetchall()
    if not rows:
        return "There is nothing in your pipeline yet."
    parts = [f"{r['c']} {r['stage'].replace('_', ' ')}" for r in rows]
    return "You have " + ", ".join(parts) + "."
