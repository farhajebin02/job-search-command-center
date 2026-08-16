from datetime import datetime, timezone


def record_interview(conn, job_id: int, when: str, round_label: str,
                     calendar_event_id: str | None) -> dict:
    app = conn.execute("SELECT * FROM application WHERE job_id=?", (job_id,)).fetchone()
    if app is None:
        raise ValueError(f"Job {job_id} is not tracked yet")
    cur = conn.execute(
        """INSERT INTO interview (application_id, round_label, scheduled_at,
             calendar_event_id, location, notes) VALUES (?,?,?,?,'','')""",
        (app["id"], round_label, when, calendar_event_id))
    conn.commit()
    return dict(conn.execute("SELECT * FROM interview WHERE id=?",
                             (cur.lastrowid,)).fetchone())


def set_calendar_event(conn, interview_id: int, calendar_event_id: str) -> None:
    """Attach a Google event to an interview already on record."""
    conn.execute("UPDATE interview SET calendar_event_id=? WHERE id=?",
                 (calendar_event_id, interview_id))
    conn.commit()


def upcoming(conn) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    rows = conn.execute(
        """SELECT i.*, j.title, j.company FROM interview i
           JOIN application a ON a.id = i.application_id
           JOIN job j ON j.id = a.job_id
           WHERE i.scheduled_at > ? ORDER BY i.scheduled_at""", (now,))
    return [dict(r) for r in rows]
