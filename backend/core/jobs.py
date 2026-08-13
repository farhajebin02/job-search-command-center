import json
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx

SEED = Path(__file__).parent.parent / "data" / "seed_chennai.json"
ADZUNA_URL = "https://api.adzuna.com/v1/api/jobs/in/search/1"


def normalize_adzuna(raw: dict) -> dict:
    return {
        "source": "adzuna",
        "source_id": str(raw.get("id", "")),
        "title": raw.get("title", ""),
        "company": (raw.get("company") or {}).get("display_name", ""),
        "location": (raw.get("location") or {}).get("display_name", ""),
        "description": raw.get("description", ""),
        "salary_min": raw.get("salary_min"),
        "salary_max": raw.get("salary_max"),
        "apply_url": raw.get("redirect_url", ""),
        "posted_at": raw.get("created", ""),
    }


def query_from_profile(profile: dict) -> tuple[str, str]:
    titles = profile.get("titles") or []
    skills = profile.get("skills") or []
    locations = profile.get("locations") or []
    what = titles[0] if titles else (skills[0] if skills else "software engineer")
    where = locations[0] if locations else "India"
    return what, where


def fetch_adzuna(what: str, where: str, limit: int = 20) -> list[dict]:
    resp = httpx.get(ADZUNA_URL, params={
        "app_id": os.environ["ADZUNA_APP_ID"],
        "app_key": os.environ["ADZUNA_APP_KEY"],
        "what": what, "where": where, "results_per_page": limit,
    }, timeout=15)
    resp.raise_for_status()
    return [normalize_adzuna(r) for r in resp.json().get("results", [])]


def load_seed() -> list[dict]:
    return json.loads(SEED.read_text(encoding="utf-8"))


def _upsert(conn, job: dict) -> int:
    conn.execute(
        """INSERT INTO job (source, source_id, title, company, location,
              description, salary_min, salary_max, apply_url, posted_at, fetched_at)
           VALUES (:source,:source_id,:title,:company,:location,:description,
              :salary_min,:salary_max,:apply_url,:posted_at,:fetched_at)
           ON CONFLICT(source, source_id) DO UPDATE SET
              title=excluded.title, description=excluded.description,
              apply_url=excluded.apply_url, fetched_at=excluded.fetched_at""",
        {**job, "fetched_at": datetime.now(timezone.utc).isoformat()},
    )
    return conn.execute(
        "SELECT id FROM job WHERE source=? AND source_id=?",
        (job["source"], job["source_id"]),
    ).fetchone()["id"]


def fetch_jobs(conn, what: str, where: str) -> list[dict]:
    try:
        found = fetch_adzuna(what, where)
    except Exception:
        found = []
    if not found:
        found = load_seed()

    ids = [_upsert(conn, j) for j in found]
    conn.execute(
        "INSERT INTO fetch_run (query, source, ran_at, job_ids_json) VALUES (?,?,?,?)",
        (f"{what} | {where}", found[0]["source"] if found else "none",
         datetime.now(timezone.utc).isoformat(), json.dumps(ids)),
    )
    conn.commit()
    return [dict(r) for r in conn.execute(
        f"SELECT * FROM job WHERE id IN ({','.join('?' * len(ids))})", ids
    )] if ids else []


def last_fetch(conn) -> list[dict]:
    row = conn.execute(
        "SELECT job_ids_json FROM fetch_run ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return []
    ids = json.loads(row["job_ids_json"])
    if not ids:
        return []
    return [dict(r) for r in conn.execute(
        f"SELECT * FROM job WHERE id IN ({','.join('?' * len(ids))})", ids
    )]
