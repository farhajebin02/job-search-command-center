import asyncio
import logging
import multiprocessing
import os
import sys
import threading
import uuid

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

logger = logging.getLogger("jcc.api")

# See agent/worker.py for why: this venv's multiprocessing "spawn" respawn
# resolves to the base interpreter instead of the venv's own python.exe.
multiprocessing.set_executable(sys.executable)

#: Rooms are named per page load. The prefix is what makes the old ones
#: identifiable so they can be cleared.
ROOM_PREFIX = "command-center-"


def reap_rooms(prefix: str) -> None:
    """Delete rooms left over from earlier page loads.

    `close_on_disconnect=False` keeps an agent session alive after the browser
    leaves, so an abandoned room holds a job process open. Enough of those and
    the worker reports itself at full capacity and stops accepting new jobs.
    """
    async def _run() -> None:
        client = lk.LiveKitAPI(
            url=os.environ["LIVEKIT_URL"].replace("wss://", "https://"),
            api_key=os.environ["LIVEKIT_API_KEY"],
            api_secret=os.environ["LIVEKIT_API_SECRET"],
        )
        try:
            rooms = (await client.room.list_rooms(lk.ListRoomsRequest())).rooms
            for r in rooms:
                if r.name.startswith(prefix):
                    await client.room.delete_room(lk.DeleteRoomRequest(room=r.name))
                    logger.info("cleared abandoned room %s", r.name)
        finally:
            await client.aclose()

    asyncio.run(_run())


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
    # FastAPI runs sync `def` endpoints in a threadpool, so one shared
    # connection gets driven from several threads at once. sqlite3 does not
    # serialise that: concurrent statements clobber each other's cursor state
    # and columns come back as None mid-iteration, which surfaces as
    # TypeError/IndexError on rows that are perfectly valid on disk. The 500s
    # that causes reach the browser without CORS headers (ServerErrorMiddleware
    # sits outside CORSMiddleware), so the frontend only ever sees "Failed to
    # fetch". Connections are cheap; give each thread its own. Scoped to the
    # app rather than the module so each test's DB_PATH gets a fresh set.
    _local = threading.local()

    def db():
        conn = getattr(_local, "conn", None)
        if conn is None:
            conn = _local.conn = connect()
        return conn

    init_db(db())

    @app.get("/api/token")
    def token(identity: str = Query(...), room: str | None = Query(None)):
        if room is None:
            # A fresh room per page load. LiveKit dispatches an agent job when a
            # room is created, so a fixed name leaves any room that outlived a
            # worker restart permanently agent-less — and reloading rejoins the
            # same dead room rather than making a new one.
            try:
                reap_rooms(ROOM_PREFIX)
            except Exception:
                # Housekeeping only. An unreachable LiveKit must not stop the
                # user getting a token.
                logger.exception("could not clear abandoned rooms")
            room = f"{ROOM_PREFIX}{uuid.uuid4().hex[:12]}"

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
        conn = db()
        save_profile(conn, data, raw_text=text)
        profile = get_profile(conn)
        what, where = query_from_profile(profile)
        jobs = fetch_jobs(conn, what, where)
        score_jobs(conn, [j["id"] for j in jobs])
        return {"profile": profile, "jobs": _decorate(conn, jobs)}

    @app.get("/api/jobs")
    def jobs():
        conn = db()
        return {"jobs": _decorate(conn, last_fetch(conn))}

    @app.get("/api/applications")
    def applications(stage: str | None = Query(None)):
        return {"applications": tracker.list_applications(db(), stage)}

    @app.post("/api/applications/{job_id}/apply")
    def apply(job_id: int):
        return {"application": tracker.mark_applied(db(), job_id)}

    @app.post("/api/applications/{job_id}/stage")
    def move(job_id: int, stage: str = Body(..., embed=True)):
        try:
            return {"application": tracker.advance_stage(db(), job_id, stage)}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/api/search")
    def search(q: str = Query("")):
        return {"jobs": _find_jobs(db(), q)}

    return app


app = create_app()
