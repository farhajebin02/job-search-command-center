from datetime import datetime, timezone

STAGES = ["saved", "applied", "screening", "round_1", "round_2",
          "final", "offer", "rejected"]
INTERVIEWING = ["screening", "round_1", "round_2", "final"]
STAGE_ORDER = {s: i for i, s in enumerate(STAGES)}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get(conn, job_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM application WHERE job_id=?", (job_id,)).fetchone()
    return dict(row) if row else None


def _upsert(conn, job_id: int, stage: str, applied: bool) -> dict:
    now = _now()
    conn.execute(
        """
        INSERT INTO application (job_id, stage, applied_at, updated_at, notes)
        VALUES (:job_id, :stage, :applied_at, :updated_at, '')
        ON CONFLICT(job_id) DO UPDATE SET
            stage = CASE
                WHEN (CASE application.stage
                        WHEN 'saved' THEN 0 WHEN 'applied' THEN 1 WHEN 'screening' THEN 2
                        WHEN 'round_1' THEN 3 WHEN 'round_2' THEN 4 WHEN 'final' THEN 5
                        WHEN 'offer' THEN 6 WHEN 'rejected' THEN 7 END) <= :stage_order
                THEN excluded.stage
                ELSE application.stage
            END,
            updated_at = excluded.updated_at,
            applied_at = COALESCE(application.applied_at, excluded.applied_at)
        """,
        {"job_id": job_id, "stage": stage,
         "applied_at": now if applied else None, "updated_at": now,
         "stage_order": STAGE_ORDER[stage]},
    )
    conn.commit()
    return _get(conn, job_id)


def save_job(conn, job_id: int) -> dict:
    return _upsert(conn, job_id, "saved", applied=False)


def mark_applied(conn, job_id: int) -> dict:
    return _upsert(conn, job_id, "applied", applied=True)


#: Spoken forms that mean a stage but do not spell it. Nobody says "round_2".
_SPOKEN = {
    "one": "1", "two": "2", "three": "3",
    "first": "1", "second": "2", "third": "3",
}

#: Words for a phase of the process rather than a specific round.
_ALIASES = {
    "interviewing": "screening",
    "interview": "screening",
    "phone_screen": "screening",
    "offered": "offer",
    "reject": "rejected",
    "saved_for_later": "saved",
}


#: Nouns for "a step in the process". They name no stage on their own, so when
#: one trails a phase — "the screening round", "the offer stage" — it is filler.
_PHASE_NOUNS = {"round", "stage", "step"}


def normalise_stage(stage: str) -> str | None:
    """Map what a person says onto a stored stage, or None if it isn't one."""
    s = (stage or "").strip().lower().replace("-", " ").replace("_", " ")
    words = [_SPOKEN.get(w, w) for w in s.split()]

    # "round one" and "first round" are the same request said in either order.
    if len(words) == 2 and "round" in words:
        other = next(w for w in words if w != "round")
        if other.isdigit():
            return f"round_{other}" if f"round_{other}" in STAGES else None

    # Otherwise a trailing phase noun modifies the stage rather than naming it:
    # "screening round" is the screening stage. Guarded on there being a stage
    # name left over, so a bare "round" stays ambiguous and is rejected.
    if len(words) > 1 and words[-1] in _PHASE_NOUNS:
        words = words[:-1]

    s = "_".join(words)
    s = _ALIASES.get(s, s)
    return s if s in STAGES else None


def advance_stage(conn, job_id: int, stage: str) -> dict:
    resolved = normalise_stage(stage)
    if resolved is None:
        raise ValueError(f"Unknown stage: {stage}")
    stage = resolved
    now = _now()
    if _get(conn, job_id) is None:
        # An explicit stage change starts tracking a job the user never saved
        # or applied to. Any stage at or past "applied" implies an application
        # exists, so stamp applied_at to match.
        applied = STAGE_ORDER[stage] >= STAGE_ORDER["applied"]
        conn.execute(
            "INSERT INTO application (job_id, stage, applied_at, updated_at, notes) "
            "VALUES (?,?,?,?,'')",
            (job_id, stage, now if applied else None, now),
        )
    else:
        # Direct UPDATE, not _upsert: this is the user correcting the record,
        # so it must be free to regress to an earlier stage.
        conn.execute("UPDATE application SET stage=?, updated_at=? WHERE job_id=?",
                     (stage, now, job_id))
    conn.commit()
    return _get(conn, job_id)


def list_applications(conn, stage: str | None = None) -> list[dict]:
    sql = ("SELECT a.*, j.title, j.company, j.apply_url FROM application a "
           "JOIN job j ON j.id = a.job_id")
    if stage == "interviewing":
        sql += f" WHERE a.stage IN ({','.join('?' * len(INTERVIEWING))})"
        sql += " ORDER BY a.updated_at DESC"
        return [dict(r) for r in conn.execute(sql, INTERVIEWING)]
    if stage:
        return [dict(r) for r in conn.execute(
            sql + " WHERE a.stage=? ORDER BY a.updated_at DESC", (stage,))]
    return [dict(r) for r in conn.execute(sql + " ORDER BY a.updated_at DESC")]


def pipeline_summary(conn) -> str:
    rows = conn.execute(
        "SELECT stage, COUNT(*) c FROM application GROUP BY stage").fetchall()
    if not rows:
        return "There is nothing in your pipeline yet."
    parts = [f"{r['c']} {r['stage'].replace('_', ' ')}" for r in rows]
    return "You have " + ", ".join(parts) + "."
