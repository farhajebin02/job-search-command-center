import json
from datetime import datetime, timezone

from core.gemini import generate_json
from core.profile import get_profile

BATCH_SIZE = 10

SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "score": {"type": "integer"},
                    "matched_skills": {"type": "array", "items": {"type": "string"}},
                    "gaps": {"type": "array", "items": {"type": "string"}},
                    "rationale": {"type": "string"},
                },
                "required": ["job_id", "score", "matched_skills", "gaps", "rationale"],
            },
        }
    },
    "required": ["results"],
}


def build_scoring_prompt(profile: dict, jobs: list[dict]) -> str:
    lines = [
        "Score each job 0-100 against the CANDIDATE below.",
        "Rules: judge only against what the candidate profile states; never invent "
        "experience. Gaps must be concrete and checkable (\"no Kubernetes experience "
        "listed\"), never vague (\"could be stronger\"). rationale is exactly one "
        "sentence. Echo job_id back exactly as given.",
        "",
        f"CANDIDATE: {profile.get('seniority')}, "
        f"{profile.get('years_experience')} years. "
        f"Titles: {', '.join(profile.get('titles') or [])}. "
        f"Skills: {', '.join(profile.get('skills') or [])}.",
        "",
    ]
    for j in jobs:
        lines.append(
            f"JOB {j['id']} :: {j['title']} at {j['company']} ({j['location']}) :: "
            f"{(j.get('description') or '')[:1200]}"
        )
    return "\n".join(lines)


def score_jobs(conn, job_ids: list[int]) -> list[dict]:
    profile = get_profile(conn)
    if profile is None:
        raise ValueError("No profile stored; upload a resume before scoring.")

    written = []
    for start in range(0, len(job_ids), BATCH_SIZE):
        chunk = job_ids[start:start + BATCH_SIZE]
        jobs = [dict(r) for r in conn.execute(
            f"SELECT * FROM job WHERE id IN ({','.join('?' * len(chunk))})", chunk)]
        if not jobs:
            continue
        data = generate_json(build_scoring_prompt(profile, jobs), SCORE_SCHEMA)
        for r in data.get("results", []):
            conn.execute(
                """INSERT INTO match (job_id, profile_id, score, matched_skills_json,
                     gaps_json, rationale, scored_at) VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(job_id, profile_id) DO UPDATE SET
                     score=excluded.score,
                     matched_skills_json=excluded.matched_skills_json,
                     gaps_json=excluded.gaps_json,
                     rationale=excluded.rationale, scored_at=excluded.scored_at""",
                (int(r["job_id"]), profile["id"], r["score"],
                 json.dumps(r["matched_skills"]), json.dumps(r["gaps"]),
                 r["rationale"], datetime.now(timezone.utc).isoformat()))
            written.append(r)
    conn.commit()
    return written


def get_matches(conn, job_ids: list[int]) -> dict[int, dict]:
    if not job_ids:
        return {}
    out = {}
    for row in conn.execute(
        f"SELECT * FROM match WHERE job_id IN ({','.join('?' * len(job_ids))})",
        job_ids,
    ):
        m = dict(row)
        m["matched_skills"] = json.loads(m.pop("matched_skills_json"))
        m["gaps"] = json.loads(m.pop("gaps_json"))
        out[m["job_id"]] = m
    return out
