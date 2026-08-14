import json
from datetime import datetime, timezone

from core.gemini import generate_json
from core.scoring import get_matches

QUESTIONS_SCHEMA = {
    "type": "object",
    "properties": {"questions": {"type": "array", "items": {"type": "string"}}},
    "required": ["questions"],
}


def build_questions(conn, job_id: int) -> list[str]:
    job = dict(conn.execute("SELECT * FROM job WHERE id=?", (job_id,)).fetchone())
    m = get_matches(conn, [job_id]).get(job_id) or {"gaps": []}
    gaps = "; ".join(m["gaps"]) or "none recorded"

    prompt = (
        "Write exactly three interview questions for this role. "
        "At least one must probe the candidate's recorded gaps directly. "
        "Keep each question to one sentence.\n\n"
        f"ROLE: {job['title']} at {job['company']}\n"
        f"DESCRIPTION: {(job.get('description') or '')[:1500]}\n"
        f"CANDIDATE GAPS: {gaps}"
    )
    try:
        return generate_json(prompt, QUESTIONS_SCHEMA)["questions"]
    except Exception:
        return [
            f"Walk me through your experience relevant to {job['title']}.",
            f"How would you approach the core responsibilities at {job['company']}?",
            f"Your profile shows these gaps: {gaps}. How would you close them?",
        ]


def save_session(conn, job_id: int, transcript: str, feedback: dict) -> int:
    cur = conn.execute(
        """INSERT INTO mock_session (job_id, started_at, ended_at, transcript,
             feedback_json) VALUES (?,?,?,?,?)""",
        (job_id, datetime.now(timezone.utc).isoformat(),
         datetime.now(timezone.utc).isoformat(), transcript, json.dumps(feedback)))
    conn.commit()
    return cur.lastrowid
