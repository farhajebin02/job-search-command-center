import os

from dotenv import load_dotenv
from fastapi import Body, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from livekit import api as lk

from core.db import connect, init_db
from core.gemini import generate_json
from core.jobs import fetch_jobs, last_fetch, query_from_profile
from core.profile import (PROFILE_SCHEMA, build_profile_prompt, extract_text,
                          get_profile, save_profile)
from core.scoring import get_matches, score_jobs
from core.search import find_jobs as _find_jobs
from core import tracker

load_dotenv()


def _decorate(conn, jobs: list[dict]) -> list[dict]:
    ids = [j["id"] for j in jobs]
    matches = get_matches(conn, ids)
    stages: dict[int, str] = {}
    if ids:
        placeholders = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT job_id, stage FROM application WHERE job_id IN ({placeholders})",
            ids,
        )
        stages = {row["job_id"]: row["stage"] for row in rows}
    return [{**j, "match": matches.get(j["id"]), "stage": stages.get(j["id"])}
            for j in jobs]


def create_app() -> FastAPI:
    app = FastAPI(title="Job Command Center")
    app.add_middleware(
        CORSMiddleware, allow_origins=["http://localhost:3000"],
        allow_methods=["*"], allow_headers=["*"],
    )
    conn = connect()
    init_db(conn)

    @app.get("/api/token")
    def token(identity: str = Query(...), room: str = Query("command-center")):
        jwt = (lk.AccessToken(os.environ["LIVEKIT_API_KEY"],
                              os.environ["LIVEKIT_API_SECRET"])
               .with_identity(identity)
               .with_grants(lk.VideoGrants(room_join=True, room=room))
               .to_jwt())
        return {"token": jwt, "url": os.environ["LIVEKIT_URL"], "room": room}

    @app.post("/api/upload")
    async def upload(file: UploadFile = File(...)):
        if not (file.filename or "").lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF resumes are accepted")
        text = extract_text(await file.read())
        if not text.strip():
            raise HTTPException(status_code=400, detail="No text found in that PDF")
        data = generate_json(build_profile_prompt(text), PROFILE_SCHEMA)
        save_profile(conn, data, raw_text=text)
        profile = get_profile(conn)
        what, where = query_from_profile(profile)
        jobs = fetch_jobs(conn, what, where)
        score_jobs(conn, [j["id"] for j in jobs])
        return {"profile": profile, "jobs": _decorate(conn, jobs)}

    @app.get("/api/jobs")
    def jobs():
        return {"jobs": _decorate(conn, last_fetch(conn))}

    @app.get("/api/applications")
    def applications(stage: str | None = Query(None)):
        return {"applications": tracker.list_applications(conn, stage)}

    @app.post("/api/applications/{job_id}/apply")
    def apply(job_id: int):
        return {"application": tracker.mark_applied(conn, job_id)}

    @app.post("/api/applications/{job_id}/stage")
    def move(job_id: int, stage: str = Body(..., embed=True)):
        try:
            return {"application": tracker.advance_stage(conn, job_id, stage)}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/api/search")
    def search(q: str = Query("")):
        return {"jobs": _find_jobs(conn, q)}

    return app


app = create_app()
