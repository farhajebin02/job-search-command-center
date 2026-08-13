import io
import json
from datetime import datetime, timezone

from pypdf import PdfReader

PROFILE_SCHEMA = {
    "type": "object",
    "properties": {
        "full_name": {"type": "string"},
        "email": {"type": "string"},
        "years_experience": {"type": "number"},
        "seniority": {"type": "string"},
        "skills": {"type": "array", "items": {"type": "string"}},
        "titles": {"type": "array", "items": {"type": "string"}},
        "locations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["full_name", "email", "years_experience", "seniority",
                 "skills", "titles", "locations"],
}


def extract_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def build_profile_prompt(resume_text: str) -> str:
    return (
        "Extract a structured candidate profile from this resume. "
        "Use only what the resume states; never infer or invent experience. "
        "seniority must be one of: junior, mid, senior, lead.\n\n"
        f"RESUME:\n{resume_text}"
    )


def save_profile(conn, data: dict, raw_text: str) -> int:
    cur = conn.execute(
        """INSERT INTO profile (full_name, email, years_experience, seniority,
           skills_json, titles_json, locations_json, raw_text, created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (data["full_name"], data["email"], data["years_experience"],
         data["seniority"], json.dumps(data["skills"]),
         json.dumps(data["titles"]), json.dumps(data["locations"]),
         raw_text, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    return cur.lastrowid


def get_profile(conn) -> dict | None:
    row = conn.execute(
        "SELECT * FROM profile ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    p = dict(row)
    p["skills"] = json.loads(p.pop("skills_json"))
    p["titles"] = json.loads(p.pop("titles_json"))
    p["locations"] = json.loads(p.pop("locations_json"))
    return p
