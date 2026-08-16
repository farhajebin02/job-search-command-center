"""What the co-pilot can see.

Without this the agent knows nothing about the jobs on screen. Asked to
"change the Whirlpool one to interviewing" it has no id to act on, so it
either burns a round trip on a lookup — roughly 285ms to us-central1 — or
invents one. Injecting the feed each turn removes the guess.
"""

from datetime import datetime

from agent.calendar import IST, IST_NAME
from core.jobs import last_fetch
from core.scoring import get_matches

#: Enough for the agent to resolve anything the user can reasonably refer to,
#: without adding a page of tokens to every single turn.
MAX_JOBS = 20


def today(now: datetime | None = None) -> str:
    """The date the user is living in.

    The scheduling tools take ISO 8601, but users speak in "Friday at 3". With
    no date in context the model resolves that against its training data and
    books the wrong Friday — frequently one already in the past. One line.
    """
    now = now or datetime.now(IST)
    return (f"Today is {now.strftime('%A %d %B %Y')}, {now.strftime('%H:%M')} "
            f"in {IST_NAME}. Resolve every relative time the user says — "
            "\"Friday\", \"tomorrow at 3\", \"next week\" — against this date, "
            "and pass the result to tools as an ISO 8601 datetime.")


def current_jobs(conn) -> str:
    """The feed as the agent should see it: one line per job, ranked the same
    way the work surface ranks them."""
    jobs = last_fetch(conn)
    if not jobs:
        return "The job feed is empty — no jobs have been fetched yet."

    ids = [j["id"] for j in jobs]
    matches = get_matches(conn, ids)
    stages = {}
    if ids:
        placeholders = ",".join("?" * len(ids))
        stages = {r["job_id"]: r["stage"] for r in conn.execute(
            f"SELECT job_id, stage FROM application WHERE job_id IN ({placeholders})",
            ids)}

    # Unscored last rather than first, matching the work surface.
    ranked = sorted(jobs, key=lambda j: matches.get(j["id"], {}).get("score", -1),
                    reverse=True)

    lines = []
    for j in ranked[:MAX_JOBS]:
        m = matches.get(j["id"])
        score = f"score {m['score']}" if m else "unscored"
        stage = stages.get(j["id"]) or "not tracked"
        lines.append(f"#{j['id']} {j['title']} · {j['company']} · {score} · {stage}")

    header = "Jobs currently on screen (id, title, company, score, stage):"
    if len(ranked) > MAX_JOBS:
        # Say the list is partial, or the agent will report a job as
        # non-existent when it is simply past the cap.
        header = (f"Top {MAX_JOBS} of {len(ranked)} jobs currently on screen "
                  "(id, title, company, score, stage). More exist beyond these:")
    return header + "\n" + "\n".join(lines)
