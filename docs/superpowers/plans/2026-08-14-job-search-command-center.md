# Job Search Command Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single-shell, voice-driven job search command center where a LiveKit agent fetches, scores, applies to, tracks, retrieves, and schedules interviews for jobs, plus runs mock interviews — demoable end to end by Sunday 2026-08-16.

**Architecture:** Three processes. A Python FastAPI server (`uvicorn`) serves upload, LiveKit tokens, and reads. A separate Python LiveKit agent worker holds the voice session and calls the same core service modules **in-process** (no HTTP hop inside the voice loop). A Next.js App Router frontend is a pure client: the LiveKit room provider lives in the root layout above all route groups, shell chrome lives in `(shell)/layout.tsx`, and only the work surface is a route. Both Python processes share one SQLite file in WAL mode.

**Tech Stack:** Python 3.12, `livekit-agents`, `google-genai` (Vertex), FastAPI + uvicorn, `pypdf`, SQLite (WAL), pytest · Next.js App Router, TypeScript, Tailwind, shadcn/ui, Lucide, Framer Motion, `@livekit/components-react` · Adzuna API, Google Workspace MCP

**Spec:** `docs/superpowers/specs/2026-08-14-job-search-command-center-design.md`

## Global Constraints

- **Deadline:** Sunday 2026-08-16, end of day. Demo recorded by 17:00 Sunday.
- **Tripwires are binding.** A (23:00 Fri), B (13:00 Sat), C (22:00 Sat), D (12:00 Sun). At each, either the stated capability works or the stated cut is applied immediately. See spec §10.
- **Cut line removes depth, never a stage** (spec §12). All six spine stages must work once each. Never cut: empty state, loading skeletons, recorded video.
- **Python 3.12.** Verified absent on this machine — only the Windows Store alias stub is on `PATH`. Node 22.14.0 is present.
- **Never hardcode model IDs from memory.** The Gemini Live model ID, the `livekit-agents` realtime class path, and the `google-genai` client surface are all recorded in `docs/verified-versions.md` by Task 0.6. Every later task reads that file rather than trusting this plan's illustrative snippets.
- **Voice marks state; clicks open URLs.** `mark_applied` never calls `window.open`. See spec §7.
- **The LiveKit provider lives in `app/layout.tsx`**, above all route groups. Moving it into `(shell)/layout.tsx` tears down the voice session on navigation to `/practice`.
- **SQLite runs in WAL mode.** Two Python processes write to it.
- **Dark theme only.** Lucide icons, no emoji. All motion respects `prefers-reduced-motion`.
- **Env vars** (all in `backend/.env`, loaded by both processes):
  `GOOGLE_APPLICATION_CREDENTIALS`, `GCP_PROJECT_ID`, `GCP_LOCATION`,
  `GEMINI_LIVE_MODEL`, `GEMINI_BATCH_MODEL`,
  `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`,
  `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `DB_PATH`

---

# Phase 0 — Friday night: setup and one spike

**Phase 0 is verification-driven, not test-driven.** You cannot write a failing test for "install Python." Each task states an exact command and the exact output that means success. Build no product code in this phase.

### Task 0.1: Install Python 3.12

**Files:**
- Create: `docs/verified-versions.md`

- [ ] **Step 1: Confirm the current state**

Run: `python --version`
Expected: fails with "The file cannot be accessed by the system" (the Windows Store alias stub). This is the known starting state.

- [ ] **Step 2: Install Python 3.12**

Run: `winget install --id Python.Python.3.12 -e --source winget`

If `winget` is unavailable, download the 64-bit installer from `https://www.python.org/downloads/release/python-3120/` and run it with "Add python.exe to PATH" checked.

- [ ] **Step 3: Open a NEW shell and verify**

The current shell has a stale `PATH`. Open a new terminal.

Run: `py -3.12 --version`
Expected: `Python 3.12.x`

- [ ] **Step 4: Disable the Store alias so `python` resolves correctly**

Open Settings → Apps → Advanced app settings → App execution aliases, and turn **off** both `python.exe` and `python3.exe`.

Run: `python --version`
Expected: `Python 3.12.x`

- [ ] **Step 5: Record it**

Create `docs/verified-versions.md`:

```markdown
# Verified Versions

Recorded during Phase 0. Later tasks read values from this file rather than
guessing. Update in place if anything changes.

| What | Value | Verified |
|---|---|---|
| Python | 3.12.x | 2026-08-14 |
```

- [ ] **Step 6: Commit**

```bash
git add docs/verified-versions.md
git commit -m "chore: record verified Python version"
```

---

### Task 0.2: Backend skeleton and dependencies

**Files:**
- Create: `backend/pyproject.toml`, `backend/.env.example`, `backend/.gitignore`
- Create: `backend/core/__init__.py`, `backend/agent/__init__.py`, `backend/api/__init__.py`, `backend/tests/__init__.py`

**Interfaces:**
- Produces: a working venv at `backend/.venv` and importable packages `core`, `api`, `agent`.

- [ ] **Step 1: Create the venv**

```bash
cd backend
py -3.12 -m venv .venv
```

- [ ] **Step 2: Write `backend/pyproject.toml`**

```toml
[project]
name = "job-command-center"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "livekit-agents[google]",
    "google-genai",
    "fastapi",
    "uvicorn[standard]",
    "python-dotenv",
    "pypdf",
    "httpx",
    "python-multipart",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio", "respx"]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 3: Install**

```bash
.venv/Scripts/python -m pip install --upgrade pip
.venv/Scripts/python -m pip install -e ".[dev]"
```

Expected: completes without error. Note the resolved `livekit-agents` version from the output — Task 0.6 records it.

- [ ] **Step 4: Create package markers**

Create four empty files: `backend/core/__init__.py`, `backend/api/__init__.py`, `backend/agent/__init__.py`, `backend/tests/__init__.py`.

- [ ] **Step 5: Write `backend/.env.example`**

```
GOOGLE_APPLICATION_CREDENTIALS=./secrets/vertex-sa.json
GCP_PROJECT_ID=
GCP_LOCATION=us-central1
GEMINI_LIVE_MODEL=
GEMINI_BATCH_MODEL=
LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
ADZUNA_APP_ID=
ADZUNA_APP_KEY=
DB_PATH=./tracker.db
```

- [ ] **Step 6: Write `backend/.gitignore`**

```
.venv/
secrets/
.env
tracker.db
tracker.db-wal
tracker.db-shm
__pycache__/
.pytest_cache/
```

- [ ] **Step 7: Verify imports work**

Run: `.venv/Scripts/python -c "import livekit.agents, google.genai, fastapi, pypdf; print('ok')"`
Expected: `ok`

- [ ] **Step 8: Commit**

```bash
git add backend/pyproject.toml backend/.env.example backend/.gitignore backend/core backend/api backend/agent backend/tests
git commit -m "chore: scaffold Python backend packages"
```

---

### Task 0.3: Vertex AI service account

**Files:**
- Modify: `backend/.env` (created from `.env.example`, never committed)
- Modify: `docs/verified-versions.md`

The existing Workspace MCP credentials are **user OAuth** and will not authenticate Vertex. A service account is required.

- [ ] **Step 1: Install gcloud**

Run: `winget install --id Google.CloudSDK -e`

Open a new shell. Run: `gcloud --version`
Expected: prints SDK version.

- [ ] **Step 2: Authenticate and select a project**

```bash
gcloud auth login
gcloud projects list
gcloud config set project <YOUR_PROJECT_ID>
```

- [ ] **Step 3: Enable the Vertex AI API**

```bash
gcloud services enable aiplatform.googleapis.com
```

- [ ] **Step 4: Create the service account and key**

```bash
gcloud iam service-accounts create job-command-center --display-name="Job Command Center"
gcloud projects add-iam-policy-binding <YOUR_PROJECT_ID> \
  --member="serviceAccount:job-command-center@<YOUR_PROJECT_ID>.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"
mkdir -p backend/secrets
gcloud iam service-accounts keys create backend/secrets/vertex-sa.json \
  --iam-account=job-command-center@<YOUR_PROJECT_ID>.iam.gserviceaccount.com
```

- [ ] **Step 5: Fill `backend/.env`**

Copy `.env.example` to `.env`. Set `GCP_PROJECT_ID` and `GOOGLE_APPLICATION_CREDENTIALS=./secrets/vertex-sa.json`. Leave model IDs empty — Task 0.6 fills them.

- [ ] **Step 6: Verify the credential actually authenticates**

Run from `backend/`:

```bash
.venv/Scripts/python -c "
from google import genai
import os
from dotenv import load_dotenv
load_dotenv()
c = genai.Client(vertexai=True, project=os.environ['GCP_PROJECT_ID'], location=os.environ['GCP_LOCATION'])
print([m.name for m in c.models.list()][:10])
"
```

Expected: a list of model names. If it raises a permissions error, the role binding has not propagated — wait 60s and retry once before investigating.

- [ ] **Step 7: Record and commit**

Add a row to `docs/verified-versions.md` for `google-genai` version and GCP region.

```bash
git add docs/verified-versions.md
git commit -m "chore: record Vertex AI setup"
```

---

### Task 0.4: LiveKit Cloud project

**Files:**
- Modify: `backend/.env`, `docs/verified-versions.md`

- [ ] **Step 1: Create the project**

At `https://cloud.livekit.io`, create a project. Copy the WebSocket URL (`wss://<name>.livekit.cloud`), API key, and API secret.

- [ ] **Step 2: Fill `backend/.env`**

Set `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`.

- [ ] **Step 3: Verify a token can be minted**

```bash
.venv/Scripts/python -c "
import os
from dotenv import load_dotenv
from livekit import api
load_dotenv()
t = api.AccessToken(os.environ['LIVEKIT_API_KEY'], os.environ['LIVEKIT_API_SECRET']) \
      .with_identity('smoke-test') \
      .with_grants(api.VideoGrants(room_join=True, room='smoke')) \
      .to_jwt()
print(t[:40], '...')
"
```

Expected: prints a JWT prefix. If `AccessToken` or `VideoGrants` is not found at that path, find the correct path with `python -c "from livekit import api; print(dir(api))"` and **record the correct call in `docs/verified-versions.md`** — Task 1.6 depends on it.

- [ ] **Step 4: Commit**

```bash
git add docs/verified-versions.md
git commit -m "chore: record LiveKit token API surface"
```

---

### Task 0.5: Adzuna key and Chennai coverage

**Files:**
- Modify: `backend/.env`, `docs/verified-versions.md`

- [ ] **Step 1: Register**

At `https://developer.adzuna.com/`, register and copy the App ID and App Key into `backend/.env`.

- [ ] **Step 2: Verify the India endpoint returns Chennai results**

```bash
.venv/Scripts/python -c "
import os, httpx
from dotenv import load_dotenv
load_dotenv()
r = httpx.get('https://api.adzuna.com/v1/api/jobs/in/search/1', params={
    'app_id': os.environ['ADZUNA_APP_ID'],
    'app_key': os.environ['ADZUNA_APP_KEY'],
    'what': 'backend engineer',
    'where': 'Chennai',
    'results_per_page': 10,
})
r.raise_for_status()
d = r.json()
print('count:', d.get('count'))
for j in d['results'][:3]:
    print('-', j['title'], '|', j['company']['display_name'], '|', j['redirect_url'][:60])
"
```

Expected: a non-zero count and three listings with real `redirect_url` values.

- [ ] **Step 3: Record the verdict**

Add to `docs/verified-versions.md`: the observed result count and whether coverage is usable. **If the count is under 10, the seeded fallback (Task 1.4) becomes the demo's primary source** — note that decision here so Saturday does not rediscover it.

- [ ] **Step 4: Commit**

```bash
git add docs/verified-versions.md
git commit -m "chore: record Adzuna Chennai coverage"
```

---

### Task 0.6: Verify the Gemini Live model and SDK surface

**Files:**
- Modify: `docs/verified-versions.md`, `backend/.env`

This is the task the spec singles out. Do not skip it and do not trust the snippets in this plan over what you observe.

- [ ] **Step 1: List available Live-capable models**

```bash
.venv/Scripts/python -c "
from google import genai
import os
from dotenv import load_dotenv
load_dotenv()
c = genai.Client(vertexai=True, project=os.environ['GCP_PROJECT_ID'], location=os.environ['GCP_LOCATION'])
for m in c.models.list():
    print(m.name)
" > models.txt
```

Inspect `models.txt` for a live/realtime-capable Gemini model and for the current Flash and Pro 2.5 identifiers.

- [ ] **Step 2: Inspect the livekit-agents Google plugin surface**

```bash
.venv/Scripts/python -c "
from livekit.plugins import google
print('google:', [n for n in dir(google) if not n.startswith('_')])
print('beta:', [n for n in dir(google.beta) if not n.startswith('_')])
print('realtime:', [n for n in dir(google.beta.realtime) if not n.startswith('_')])
"
```

Expected: `realtime` exposes a `RealtimeModel`. If the path differs in the installed version, **the observed path is authoritative**.

- [ ] **Step 3: Confirm the fallback pipeline exists**

Tripwire A depends on this being available, so verify it now rather than at 23:00.

```bash
.venv/Scripts/python -c "
from livekit.plugins import google
print('STT:', hasattr(google, 'STT'))
print('TTS:', hasattr(google, 'TTS'))
print('LLM:', hasattr(google, 'LLM'))
"
```

Expected: three `True` values. If any is `False`, record which plugin package supplies the missing piece.

- [ ] **Step 4: Fill in the model IDs**

Set `GEMINI_LIVE_MODEL` and `GEMINI_BATCH_MODEL` in `backend/.env` from what Step 1 actually returned.

- [ ] **Step 5: Record everything**

Add rows to `docs/verified-versions.md` for: `livekit-agents` version, the realtime model class path, the Live model ID, the batch model ID, and whether the STT/TTS/LLM fallback trio is available.

- [ ] **Step 6: Commit**

```bash
git add docs/verified-versions.md
git commit -m "chore: verify Gemini Live model and livekit-agents surface"
```

---

### Task 0.7: The spike — a bare voice conversation

**Files:**
- Create: `backend/agent/spike.py`

This is throwaway proof, not product code. Its only output is an answer to "does voice work end to end." Do not add tools, personas, or UI.

- [ ] **Step 1: Write the spike agent**

Adjust the realtime class path to whatever Task 0.6 recorded.

```python
# backend/agent/spike.py — THROWAWAY. Deleted in Task 1.11.
import os
from dotenv import load_dotenv
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.plugins import google

load_dotenv()


async def entrypoint(ctx: JobContext):
    await ctx.connect()
    session = AgentSession(
        llm=google.beta.realtime.RealtimeModel(
            model=os.environ["GEMINI_LIVE_MODEL"],
            vertexai=True,
            project=os.environ["GCP_PROJECT_ID"],
            location=os.environ["GCP_LOCATION"],
        )
    )
    await session.start(
        agent=Agent(instructions="You are a terse assistant. Reply in one sentence."),
        room=ctx.room,
    )
    await session.generate_reply(instructions="Greet the user in one short sentence.")


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
```

- [ ] **Step 2: Run the worker**

Run: `.venv/Scripts/python -m agent.spike dev`
Expected: registers with LiveKit Cloud and waits for a job.

- [ ] **Step 3: Talk to it**

Open `https://agents-playground.livekit.io`, connect it to your LiveKit Cloud project, and join a room.

Expected: the agent greets you, and it answers a spoken follow-up question. **This is the entire deliverable of Phase 0.**

- [ ] **Step 4: Record the outcome**

Add to `docs/verified-versions.md`: whether Live worked, and the observed latency impression.

- [ ] **Step 5: Commit**

```bash
git add backend/agent/spike.py docs/verified-versions.md
git commit -m "spike: bare LiveKit voice agent via Gemini Live"
```

---

### ⛔ TRIPWIRE A — 23:00 Friday

**Test:** does Task 0.7 hold a two-turn spoken conversation?

- **Yes** → stop for the night. Phase 1 starts Saturday morning.
- **No** → stop debugging Gemini Live. Rewrite `spike.py` using the STT → LLM → TTS pipeline verified in Task 0.6 Step 3, substituting `AgentSession(stt=google.STT(), llm=google.LLM(model=os.environ["GEMINI_BATCH_MODEL"]), tts=google.TTS())` for the realtime `llm=` argument, and verify that instead. Record the switch in `docs/verified-versions.md`. Every later task uses the pipeline path unchanged — the tool and persona code is identical.

Do not carry an unresolved voice stack into Saturday.

---

# Phase 1 — Saturday: the spine

TDD applies from here. Every task: failing test → run it → minimal implementation → passing test → commit.

### Task 1.1: Database schema and connection

**Files:**
- Create: `backend/core/schema.sql`, `backend/core/db.py`
- Test: `backend/tests/test_db.py`

**Interfaces:**
- Produces: `connect(db_path: str | None = None) -> sqlite3.Connection` — WAL enabled, `row_factory` set to `sqlite3.Row`. `init_db(conn: sqlite3.Connection) -> None` — idempotent schema creation.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_db.py
from core.db import connect, init_db


def test_init_db_creates_all_tables(tmp_path):
    conn = connect(str(tmp_path / "t.db"))
    init_db(conn)
    names = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert {"profile", "job", "match", "application",
            "interview", "mock_session", "fetch_run"} <= names


def test_init_db_is_idempotent(tmp_path):
    conn = connect(str(tmp_path / "t.db"))
    init_db(conn)
    init_db(conn)  # must not raise


def test_wal_mode_is_enabled(tmp_path):
    conn = connect(str(tmp_path / "t.db"))
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.db'`

- [ ] **Step 3: Write `backend/core/schema.sql`**

```sql
CREATE TABLE IF NOT EXISTS profile (
  id INTEGER PRIMARY KEY, full_name TEXT, email TEXT,
  years_experience REAL, seniority TEXT, skills_json TEXT,
  titles_json TEXT, locations_json TEXT, raw_text TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS job (
  id INTEGER PRIMARY KEY, source TEXT, source_id TEXT, title TEXT,
  company TEXT, location TEXT, description TEXT, salary_min REAL,
  salary_max REAL, apply_url TEXT, posted_at TEXT, fetched_at TEXT,
  UNIQUE(source, source_id)
);
CREATE TABLE IF NOT EXISTS match (
  id INTEGER PRIMARY KEY, job_id INTEGER, profile_id INTEGER,
  score INTEGER, matched_skills_json TEXT, gaps_json TEXT,
  rationale TEXT, scored_at TEXT, UNIQUE(job_id, profile_id)
);
CREATE TABLE IF NOT EXISTS application (
  id INTEGER PRIMARY KEY, job_id INTEGER UNIQUE, stage TEXT,
  applied_at TEXT, updated_at TEXT, notes TEXT
);
CREATE TABLE IF NOT EXISTS interview (
  id INTEGER PRIMARY KEY, application_id INTEGER, round_label TEXT,
  scheduled_at TEXT, calendar_event_id TEXT, location TEXT, notes TEXT
);
CREATE TABLE IF NOT EXISTS mock_session (
  id INTEGER PRIMARY KEY, job_id INTEGER, started_at TEXT,
  ended_at TEXT, transcript TEXT, feedback_json TEXT
);
CREATE TABLE IF NOT EXISTS fetch_run (
  id INTEGER PRIMARY KEY, query TEXT, source TEXT,
  ran_at TEXT, job_ids_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_job_company ON job(company);
CREATE INDEX IF NOT EXISTS idx_application_stage ON application(stage);
```

- [ ] **Step 4: Write `backend/core/db.py`**

```python
import os
import sqlite3
from pathlib import Path

SCHEMA = Path(__file__).parent / "schema.sql"


def connect(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or os.environ.get("DB_PATH", "./tracker.db")
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA.read_text())
    conn.commit()
```

- [ ] **Step 5: Run to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_db.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add backend/core/db.py backend/core/schema.sql backend/tests/test_db.py
git commit -m "feat: SQLite schema and WAL connection"
```

---

### Task 1.2: Resume parsing and profile extraction

**Files:**
- Create: `backend/core/profile.py`
- Test: `backend/tests/test_profile.py`

**Interfaces:**
- Consumes: `core.db.connect`, `core.db.init_db`
- Produces:
  - `extract_text(pdf_bytes: bytes) -> str`
  - `build_profile_prompt(resume_text: str) -> str`
  - `PROFILE_SCHEMA: dict` — the JSON schema passed to Gemini
  - `save_profile(conn, data: dict, raw_text: str) -> int` — returns `profile_id`
  - `get_profile(conn) -> dict | None` — most recent profile, JSON columns already decoded

- [ ] **Step 1: Write the failing test**

Gemini is not called in tests; `save_profile` takes an already-parsed dict so the deterministic half is testable without the network.

```python
# backend/tests/test_profile.py
import json
from core.db import connect, init_db
from core.profile import save_profile, get_profile, build_profile_prompt, PROFILE_SCHEMA


def _conn(tmp_path):
    c = connect(str(tmp_path / "t.db"))
    init_db(c)
    return c


def test_save_and_get_profile_roundtrips_json_columns(tmp_path):
    conn = _conn(tmp_path)
    pid = save_profile(conn, {
        "full_name": "Farha Jebin",
        "email": "f@example.com",
        "years_experience": 4.0,
        "seniority": "mid",
        "skills": ["Python", "React"],
        "titles": ["Backend Engineer"],
        "locations": ["Chennai"],
    }, raw_text="resume text")
    assert pid > 0
    p = get_profile(conn)
    assert p["full_name"] == "Farha Jebin"
    assert p["skills"] == ["Python", "React"]
    assert p["locations"] == ["Chennai"]


def test_get_profile_returns_none_when_empty(tmp_path):
    assert get_profile(_conn(tmp_path)) is None


def test_get_profile_returns_most_recent(tmp_path):
    conn = _conn(tmp_path)
    save_profile(conn, {"full_name": "First", "email": "", "years_experience": 1,
                        "seniority": "junior", "skills": [], "titles": [],
                        "locations": []}, raw_text="a")
    save_profile(conn, {"full_name": "Second", "email": "", "years_experience": 2,
                        "seniority": "mid", "skills": [], "titles": [],
                        "locations": []}, raw_text="b")
    assert get_profile(conn)["full_name"] == "Second"


def test_prompt_embeds_resume_text():
    assert "SOME RESUME" in build_profile_prompt("SOME RESUME")


def test_schema_requires_every_profile_field():
    assert set(PROFILE_SCHEMA["required"]) == {
        "full_name", "email", "years_experience", "seniority",
        "skills", "titles", "locations",
    }
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_profile.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.profile'`

- [ ] **Step 3: Write `backend/core/profile.py`**

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_profile.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/core/profile.py backend/tests/test_profile.py
git commit -m "feat: resume parsing and profile persistence"
```

---

### Task 1.3: Gemini client wrapper

**Files:**
- Create: `backend/core/gemini.py`
- Test: `backend/tests/test_gemini.py`

**Interfaces:**
- Produces: `generate_json(prompt: str, schema: dict, model: str | None = None) -> dict` — one Vertex call returning parsed JSON. Centralised here so scoring, profile extraction, and interview-question generation share one code path.

- [ ] **Step 1: Write the failing test**

The network call is stubbed; what is tested is that the response is parsed and that a bad response fails loudly rather than silently returning `{}`.

```python
# backend/tests/test_gemini.py
import json
import pytest
from core import gemini


class _Resp:
    def __init__(self, text): self.text = text


def test_generate_json_parses_response(monkeypatch):
    monkeypatch.setattr(gemini, "_call", lambda p, s, m: _Resp('{"score": 88}'))
    assert gemini.generate_json("p", {"type": "object"}, "m") == {"score": 88}


def test_generate_json_raises_on_unparseable_response(monkeypatch):
    monkeypatch.setattr(gemini, "_call", lambda p, s, m: _Resp("not json"))
    with pytest.raises(ValueError, match="did not return valid JSON"):
        gemini.generate_json("p", {"type": "object"}, "m")
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_gemini.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.gemini'`

- [ ] **Step 3: Write `backend/core/gemini.py`**

```python
import json
import os
from functools import lru_cache

from google import genai
from google.genai import types


@lru_cache(maxsize=1)
def _client():
    return genai.Client(
        vertexai=True,
        project=os.environ["GCP_PROJECT_ID"],
        location=os.environ["GCP_LOCATION"],
    )


def _call(prompt: str, schema: dict, model: str):
    return _client().models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
        ),
    )


def generate_json(prompt: str, schema: dict, model: str | None = None) -> dict:
    resp = _call(prompt, schema, model or os.environ["GEMINI_BATCH_MODEL"])
    try:
        return json.loads(resp.text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"Gemini did not return valid JSON: {resp.text!r}") from exc
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_gemini.py -v`
Expected: 2 passed

- [ ] **Step 5: Smoke-test against real Vertex**

```bash
.venv/Scripts/python -c "
from dotenv import load_dotenv; load_dotenv()
from core.gemini import generate_json
print(generate_json('Return {\"ok\": true}', {'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok']}))
"
```

Expected: `{'ok': True}`. If the `types.GenerateContentConfig` field names differ in the installed SDK, correct them here and note it in `docs/verified-versions.md`.

- [ ] **Step 6: Commit**

```bash
git add backend/core/gemini.py backend/tests/test_gemini.py
git commit -m "feat: shared Gemini structured-output client"
```

---

### Task 1.4: Job fetching — Adzuna client, normaliser, seed fallback

**Files:**
- Create: `backend/core/jobs.py`, `backend/data/seed_chennai.json`
- Test: `backend/tests/test_jobs.py`

**Interfaces:**
- Consumes: `core.db`, `core.profile.get_profile`
- Produces:
  - `normalize_adzuna(raw: dict) -> dict` — one Adzuna result → a `job` row dict
  - `query_from_profile(profile: dict) -> tuple[str, str]` — returns `(what, where)`
  - `fetch_adzuna(what: str, where: str, limit: int = 20) -> list[dict]`
  - `load_seed() -> list[dict]`
  - `fetch_jobs(conn, what: str, where: str) -> list[dict]` — fetches, falls back to seed on any failure or empty result, upserts, records a `fetch_run`, returns saved job rows with `id`
  - `last_fetch(conn) -> list[dict]` — the jobs from the most recent `fetch_run`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_jobs.py
import json
from core.db import connect, init_db
from core import jobs

RAW = {
    "id": "123", "title": "Backend Engineer",
    "company": {"display_name": "Freshworks"},
    "location": {"display_name": "Chennai, Tamil Nadu"},
    "description": "Python and Django.",
    "salary_min": 1200000, "salary_max": 1800000,
    "redirect_url": "https://adzuna.example/job/123",
    "created": "2026-08-01T00:00:00Z",
}


def _conn(tmp_path):
    c = connect(str(tmp_path / "t.db"))
    init_db(c)
    return c


def test_normalize_maps_nested_adzuna_fields():
    j = jobs.normalize_adzuna(RAW)
    assert j["source"] == "adzuna"
    assert j["source_id"] == "123"
    assert j["company"] == "Freshworks"
    assert j["location"] == "Chennai, Tamil Nadu"
    assert j["apply_url"] == "https://adzuna.example/job/123"


def test_normalize_tolerates_missing_optional_fields():
    j = jobs.normalize_adzuna({"id": "9", "title": "Dev", "redirect_url": "u"})
    assert j["company"] == ""
    assert j["salary_min"] is None


def test_query_from_profile_uses_first_title_and_location():
    what, where = jobs.query_from_profile(
        {"titles": ["Backend Engineer", "SRE"], "locations": ["Chennai"], "skills": []}
    )
    assert what == "Backend Engineer"
    assert where == "Chennai"


def test_query_from_profile_falls_back_to_skills_and_india():
    what, where = jobs.query_from_profile(
        {"titles": [], "locations": [], "skills": ["Python", "React"]}
    )
    assert what == "Python"
    assert where == "India"


def test_fetch_jobs_falls_back_to_seed_when_source_fails(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    monkeypatch.setattr(jobs, "fetch_adzuna",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    saved = jobs.fetch_jobs(conn, "backend", "Chennai")
    assert len(saved) > 0
    assert all(j["source"] == "seed" for j in saved)


def test_fetch_jobs_upserts_rather_than_duplicating(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    monkeypatch.setattr(jobs, "fetch_adzuna", lambda *a, **k: [jobs.normalize_adzuna(RAW)])
    jobs.fetch_jobs(conn, "backend", "Chennai")
    jobs.fetch_jobs(conn, "backend", "Chennai")
    assert conn.execute("SELECT COUNT(*) FROM job").fetchone()[0] == 1


def test_fetch_jobs_records_a_fetch_run(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    monkeypatch.setattr(jobs, "fetch_adzuna", lambda *a, **k: [jobs.normalize_adzuna(RAW)])
    jobs.fetch_jobs(conn, "backend", "Chennai")
    row = conn.execute("SELECT * FROM fetch_run ORDER BY id DESC LIMIT 1").fetchone()
    assert row["query"] == "backend | Chennai"
    assert len(json.loads(row["job_ids_json"])) == 1


def test_last_fetch_returns_jobs_from_most_recent_run(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    monkeypatch.setattr(jobs, "fetch_adzuna", lambda *a, **k: [jobs.normalize_adzuna(RAW)])
    jobs.fetch_jobs(conn, "backend", "Chennai")
    assert [j["source_id"] for j in jobs.last_fetch(conn)] == ["123"]


def test_last_fetch_is_empty_on_cold_db(tmp_path):
    assert jobs.last_fetch(_conn(tmp_path)) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_jobs.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.jobs'`

- [ ] **Step 3: Create the seed dataset**

Create `backend/data/seed_chennai.json` — a JSON array of at least 40 objects, each already in normalised form. Populate it with **real Chennai listings**, not invented ones: the assessment shows real apply links. Source them from a job board and copy the genuine posting URL into `apply_url`.

Each entry:

```json
[
  {
    "source": "seed",
    "source_id": "seed-001",
    "title": "Senior Backend Engineer",
    "company": "Freshworks",
    "location": "Chennai, Tamil Nadu",
    "description": "Build and scale Python services. Requires Django, PostgreSQL, and AWS. Kubernetes experience preferred.",
    "salary_min": 2000000,
    "salary_max": 3200000,
    "apply_url": "https://www.freshworks.com/company/careers/",
    "posted_at": "2026-08-10T00:00:00Z"
  }
]
```

Vary title, company, seniority, and required skills across the 40 so scoring produces a spread rather than a wall of identical numbers. Descriptions must name concrete technologies — the scorer's gap output is only as specific as its input.

- [ ] **Step 4: Write `backend/core/jobs.py`**

```python
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
```

- [ ] **Step 5: Run to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_jobs.py -v`
Expected: 9 passed

- [ ] **Step 6: Commit**

```bash
git add backend/core/jobs.py backend/data/seed_chennai.json backend/tests/test_jobs.py
git commit -m "feat: job fetching with seed fallback and fetch_run history"
```

---

### Task 1.5: Batch scoring

**Files:**
- Create: `backend/core/scoring.py`
- Test: `backend/tests/test_scoring.py`

**Interfaces:**
- Consumes: `core.gemini.generate_json`, `core.profile.get_profile`
- Produces:
  - `SCORE_SCHEMA: dict`
  - `build_scoring_prompt(profile: dict, jobs: list[dict]) -> str`
  - `score_jobs(conn, job_ids: list[int]) -> list[dict]` — batches 10 per call, writes `match` rows, returns them
  - `get_matches(conn, job_ids: list[int]) -> dict[int, dict]`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_scoring.py
from core.db import connect, init_db
from core.profile import save_profile
from core import scoring


def _setup(tmp_path):
    conn = connect(str(tmp_path / "t.db"))
    init_db(conn)
    save_profile(conn, {"full_name": "T", "email": "", "years_experience": 4,
                        "seniority": "mid", "skills": ["Python"],
                        "titles": ["Backend Engineer"], "locations": ["Chennai"]},
                 raw_text="r")
    ids = []
    for i in range(12):
        cur = conn.execute(
            """INSERT INTO job (source, source_id, title, company, location,
                 description, apply_url) VALUES (?,?,?,?,?,?,?)""",
            ("seed", f"s{i}", f"Job {i}", "Co", "Chennai", "Python work", "u"))
        ids.append(cur.lastrowid)
    conn.commit()
    return conn, ids


def test_prompt_includes_profile_skills_and_every_job(tmp_path):
    conn, ids = _setup(tmp_path)
    jobs = [dict(r) for r in conn.execute("SELECT * FROM job LIMIT 2")]
    p = {"skills": ["Python"], "seniority": "mid", "years_experience": 4,
         "titles": ["Backend Engineer"]}
    prompt = scoring.build_scoring_prompt(p, jobs)
    assert "Python" in prompt
    assert str(jobs[0]["id"]) in prompt and str(jobs[1]["id"]) in prompt


def test_score_jobs_batches_in_tens(tmp_path, monkeypatch):
    conn, ids = _setup(tmp_path)
    calls = []

    def fake(prompt, schema, model=None):
        batch = [ln for ln in prompt.splitlines() if ln.startswith("JOB ")]
        calls.append(len(batch))
        return {"results": [{"job_id": ln.split()[1], "score": 70,
                             "matched_skills": ["Python"], "gaps": ["No Kubernetes"],
                             "rationale": "Fits."} for ln in batch]}

    monkeypatch.setattr(scoring, "generate_json", fake)
    scoring.score_jobs(conn, ids)
    assert calls == [10, 2]


def test_score_jobs_writes_match_rows(tmp_path, monkeypatch):
    conn, ids = _setup(tmp_path)
    monkeypatch.setattr(scoring, "generate_json", lambda p, s, m=None: {
        "results": [{"job_id": str(i), "score": 81, "matched_skills": ["Python"],
                     "gaps": ["No Kubernetes"], "rationale": "Good."} for i in ids[:10]]})
    scoring.score_jobs(conn, ids[:10])
    row = conn.execute("SELECT * FROM match WHERE job_id=?", (ids[0],)).fetchone()
    assert row["score"] == 81
    assert row["rationale"] == "Good."


def test_score_jobs_is_idempotent_per_job(tmp_path, monkeypatch):
    conn, ids = _setup(tmp_path)
    monkeypatch.setattr(scoring, "generate_json", lambda p, s, m=None: {
        "results": [{"job_id": str(ids[0]), "score": 55, "matched_skills": [],
                     "gaps": [], "rationale": "x"}]})
    scoring.score_jobs(conn, [ids[0]])
    scoring.score_jobs(conn, [ids[0]])
    assert conn.execute("SELECT COUNT(*) FROM match").fetchone()[0] == 1


def test_get_matches_decodes_json_columns(tmp_path, monkeypatch):
    conn, ids = _setup(tmp_path)
    monkeypatch.setattr(scoring, "generate_json", lambda p, s, m=None: {
        "results": [{"job_id": str(ids[0]), "score": 90,
                     "matched_skills": ["Python"], "gaps": ["No K8s"],
                     "rationale": "y"}]})
    scoring.score_jobs(conn, [ids[0]])
    m = scoring.get_matches(conn, [ids[0]])
    assert m[ids[0]]["matched_skills"] == ["Python"]
    assert m[ids[0]]["gaps"] == ["No K8s"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_scoring.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.scoring'`

- [ ] **Step 3: Write `backend/core/scoring.py`**

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_scoring.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/core/scoring.py backend/tests/test_scoring.py
git commit -m "feat: batched Gemini job scoring"
```

---

### Task 1.6: FastAPI server — upload, token, reads

**Files:**
- Create: `backend/api/main.py`
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `core.db`, `core.profile`, `core.jobs`, `core.scoring`
- Produces: HTTP endpoints
  - `POST /api/upload` (multipart `file`) → `{profile, jobs}`
  - `GET /api/token?identity=<str>&room=<str>` → `{token, url, room}`
  - `GET /api/jobs` → `{jobs}` — last fetch, each job carrying `match`
  - `GET /api/applications` → `{applications}`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_api.py
import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("LIVEKIT_API_KEY", "devkey")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "devsecretdevsecretdevsecret")
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")
    from api.main import create_app
    return TestClient(create_app())


def test_token_returns_jwt_and_url(client):
    r = client.get("/api/token", params={"identity": "u1", "room": "cmd"})
    assert r.status_code == 200
    body = r.json()
    assert body["token"].count(".") == 2
    assert body["url"] == "wss://example.livekit.cloud"
    assert body["room"] == "cmd"


def test_token_requires_identity(client):
    assert client.get("/api/token").status_code == 422


def test_jobs_is_empty_on_cold_start(client):
    assert client.get("/api/jobs").json() == {"jobs": []}


def test_upload_rejects_non_pdf(client):
    r = client.post("/api/upload",
                    files={"file": ("cv.txt", b"hello", "text/plain")})
    assert r.status_code == 400
    assert "PDF" in r.json()["detail"]


def test_applications_is_empty_on_cold_start(client):
    assert client.get("/api/applications").json() == {"applications": []}
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_api.py -v`
Expected: FAIL — `ImportError: cannot import name 'create_app'`

- [ ] **Step 3: Write `backend/api/main.py`**

Use the token API shape recorded in Task 0.4 Step 3 if it differed from below.

```python
import os

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from livekit import api as lk

from core.db import connect, init_db
from core.gemini import generate_json
from core.jobs import fetch_jobs, last_fetch, query_from_profile
from core.profile import (PROFILE_SCHEMA, build_profile_prompt, extract_text,
                          get_profile, save_profile)
from core.scoring import get_matches, score_jobs

load_dotenv()


def _decorate(conn, jobs: list[dict]) -> list[dict]:
    matches = get_matches(conn, [j["id"] for j in jobs])
    return [{**j, "match": matches.get(j["id"])} for j in jobs]


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
    def applications():
        rows = conn.execute(
            """SELECT a.*, j.title, j.company, j.apply_url FROM application a
               JOIN job j ON j.id = a.job_id ORDER BY a.updated_at DESC""")
        return {"applications": [dict(r) for r in rows]}

    return app


app = create_app()
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_api.py -v`
Expected: 5 passed

- [ ] **Step 5: Run the server and check it live**

Run: `.venv/Scripts/python -m uvicorn api.main:app --reload --port 8000`
Then in another shell: `curl "http://localhost:8000/api/token?identity=me"`
Expected: JSON with a `token`, `url`, and `room`.

- [ ] **Step 6: Commit**

```bash
git add backend/api/main.py backend/tests/test_api.py
git commit -m "feat: FastAPI upload, token, and read endpoints"
```

---

### ⛔ TRIPWIRE B — 13:00 Saturday

**Test:** does `POST /api/upload` with a real resume PDF return scored jobs?

- **Yes** → continue to Task 1.7.
- **No** → **cut the history layer whole.** Skip Tasks 2.4 and 2.5 entirely and remove `find_jobs`/`save_job` from Task 1.11's tool list. Record the cut in `docs/verified-versions.md`. It is the newest scope and goes first.

---

### Task 1.7: Next.js scaffold and the root layout

**Files:**
- Create: `frontend/` (via `create-next-app`)
- Create: `frontend/lib/types.ts`, `frontend/lib/api.ts`
- Modify: `frontend/app/layout.tsx`, `frontend/app/globals.css`

**Interfaces:**
- Produces: `RoomShell` in `app/layout.tsx` wrapping all routes; `Job`, `Match`, `Application` types; `fetchJobs()`, `fetchApplications()`, `uploadResume(file)`, `fetchToken(identity)` in `lib/api.ts`.

- [ ] **Step 1: Scaffold**

```bash
npx create-next-app@latest frontend --typescript --tailwind --app --eslint --src-dir=false --import-alias="@/*" --no-turbopack
cd frontend
npm install @livekit/components-react @livekit/components-styles livekit-client framer-motion lucide-react
npx shadcn@latest init -d
npx shadcn@latest add card badge button skeleton
```

- [ ] **Step 2: Write `frontend/lib/types.ts`**

```typescript
export type Match = {
  score: number;
  matched_skills: string[];
  gaps: string[];
  rationale: string;
};

export type Job = {
  id: number;
  title: string;
  company: string;
  location: string;
  description: string;
  apply_url: string;
  salary_min: number | null;
  salary_max: number | null;
  match: Match | null;
};

export type Application = {
  id: number;
  job_id: number;
  stage: string;
  title: string;
  company: string;
  apply_url: string;
  updated_at: string;
};
```

- [ ] **Step 3: Write `frontend/lib/api.ts`**

```typescript
import type { Application, Job } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`${path} failed: ${r.status}`);
  return r.json();
}

export const fetchJobs = () => get<{ jobs: Job[] }>("/api/jobs");
export const fetchApplications = () =>
  get<{ applications: Application[] }>("/api/applications");
export const fetchToken = (identity: string) =>
  get<{ token: string; url: string; room: string }>(
    `/api/token?identity=${encodeURIComponent(identity)}`,
  );

export async function uploadResume(file: File) {
  const body = new FormData();
  body.append("file", file);
  const r = await fetch(`${BASE}/api/upload`, { method: "POST", body });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Upload failed");
  return r.json() as Promise<{ jobs: Job[] }>;
}
```

- [ ] **Step 4: Write `frontend/app/layout.tsx`**

The provider MUST live here, above all route groups. See Global Constraints.

```tsx
"use client";

import "@livekit/components-styles";
import "./globals.css";
import { LiveKitRoom, RoomAudioRenderer } from "@livekit/components-react";
import { useEffect, useState } from "react";
import { fetchToken } from "@/lib/api";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const [conn, setConn] = useState<{ token: string; url: string } | null>(null);

  useEffect(() => {
    fetchToken("operator").then(setConn).catch(console.error);
  }, []);

  return (
    <html lang="en" className="dark">
      <body className="bg-neutral-950 text-neutral-100 antialiased">
        {conn ? (
          <LiveKitRoom
            token={conn.token}
            serverUrl={conn.url}
            connect
            audio
            video={false}
          >
            <RoomAudioRenderer />
            {children}
          </LiveKitRoom>
        ) : (
          <div className="grid min-h-dvh place-items-center text-neutral-500">
            Connecting…
          </div>
        )}
      </body>
    </html>
  );
}
```

- [ ] **Step 5: Verify the room connects**

Run: `npm run dev`, open `http://localhost:3000` with the FastAPI server running.
Expected: "Connecting…" resolves and the LiveKit connection appears in the browser console. If it hangs, check CORS and that `/api/token` returns 200.

- [ ] **Step 6: Commit**

```bash
git add frontend
git commit -m "feat: Next.js scaffold with root-level LiveKit provider"
```

---

### Task 1.8: Shell layout — voice rail, loop spine, pipeline rail

**Files:**
- Create: `frontend/app/(shell)/layout.tsx`
- Create: `frontend/components/voice-rail.tsx`, `frontend/components/loop-spine.tsx`, `frontend/components/pipeline-rail.tsx`

**Interfaces:**
- Consumes: `@livekit/components-react` hooks, `lib/api.fetchApplications`
- Produces: the persistent chrome. Rails are fixed-width; the work surface is `children`.

- [ ] **Step 1: Write `frontend/components/voice-rail.tsx`**

```tsx
"use client";

import { useVoiceAssistant, BarVisualizer } from "@livekit/components-react";
import { Mic } from "lucide-react";

export function VoiceRail() {
  const { state, audioTrack } = useVoiceAssistant();

  return (
    <aside className="flex w-[280px] shrink-0 flex-col gap-4 border-r border-neutral-800 p-4">
      <div className="flex items-center gap-2 text-sm text-neutral-400">
        <Mic className="h-4 w-4" aria-hidden="true" />
        <span>{state === "speaking" ? "Speaking" : state === "listening" ? "Listening" : "Idle"}</span>
      </div>
      <div className="h-24 rounded-lg bg-neutral-900 p-2">
        <BarVisualizer state={state} barCount={7} trackRef={audioTrack} />
      </div>
      <div
        aria-live="polite"
        className="flex-1 overflow-y-auto rounded-lg bg-neutral-900 p-3 text-sm leading-relaxed text-neutral-300"
      >
        <p className="text-neutral-500">Transcript appears here.</p>
      </div>
    </aside>
  );
}
```

- [ ] **Step 2: Write `frontend/components/loop-spine.tsx`**

Segment-to-route mapping is fixed by spec §9.

```tsx
"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

const SEGMENTS = [
  { key: "discover", label: "Discover", href: "/" },
  { key: "score", label: "Score", href: "/" },
  { key: "apply", label: "Apply", href: "/pipeline?stage=applied" },
  { key: "track", label: "Track", href: "/pipeline?stage=interviewing" },
  { key: "schedule", label: "Schedule", href: "/pipeline?stage=interviewing" },
  { key: "practice", label: "Practice", href: "/" },
] as const;

export function LoopSpine({ counts }: { counts: Record<string, number> }) {
  const pathname = usePathname();
  const stage = useSearchParams().get("stage");

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : href.includes(stage ?? " ");

  return (
    <nav className="flex items-stretch gap-1 border-b border-neutral-800 px-4 py-2">
      {SEGMENTS.map((s) => (
        <Link
          key={s.key}
          href={s.href}
          className={`flex-1 rounded-md px-3 py-2 text-center text-xs transition-colors ${
            isActive(s.href)
              ? "bg-neutral-800 text-neutral-100"
              : "text-neutral-500 hover:bg-neutral-900"
          }`}
        >
          <span className="block">{s.label}</span>
          <span className="block font-mono tabular-nums text-sm text-neutral-300">
            {counts[s.key] ?? 0}
          </span>
        </Link>
      ))}
    </nav>
  );
}
```

- [ ] **Step 3: Write `frontend/components/pipeline-rail.tsx`**

```tsx
"use client";

import type { Application } from "@/lib/types";

const ORDER = ["saved", "applied", "screening", "round_1", "round_2",
                "final", "offer", "rejected"];

export function PipelineRail({ applications }: { applications: Application[] }) {
  const grouped = ORDER.map((stage) => ({
    stage,
    items: applications.filter((a) => a.stage === stage),
  })).filter((g) => g.items.length > 0);

  return (
    <aside className="w-[320px] shrink-0 overflow-y-auto border-l border-neutral-800 p-4">
      <h2 className="mb-3 text-sm font-medium text-neutral-400">Pipeline</h2>
      {grouped.length === 0 && (
        <p className="text-sm text-neutral-600">Nothing tracked yet.</p>
      )}
      {grouped.map((g) => (
        <details key={g.stage} open={g.stage === "applied"} className="mb-2">
          <summary className="cursor-pointer text-xs uppercase tracking-wide text-neutral-500">
            {g.stage.replace("_", " ")} ({g.items.length})
          </summary>
          <ul className="mt-2 space-y-1">
            {g.items.map((a) => (
              <li key={a.id} className="rounded-md bg-neutral-900 px-3 py-2 text-sm">
                <div className="truncate font-medium">{a.title}</div>
                <div className="truncate text-xs text-neutral-500">{a.company}</div>
              </li>
            ))}
          </ul>
        </details>
      ))}
    </aside>
  );
}
```

- [ ] **Step 4: Write `frontend/app/(shell)/layout.tsx`**

```tsx
"use client";

import { Suspense, useEffect, useState } from "react";
import { VoiceRail } from "@/components/voice-rail";
import { LoopSpine } from "@/components/loop-spine";
import { PipelineRail } from "@/components/pipeline-rail";
import { fetchApplications, fetchJobs } from "@/lib/api";
import type { Application } from "@/lib/types";

export default function ShellLayout({ children }: { children: React.ReactNode }) {
  const [apps, setApps] = useState<Application[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});

  useEffect(() => {
    const load = async () => {
      const [{ applications }, { jobs }] = await Promise.all([
        fetchApplications(), fetchJobs(),
      ]);
      setApps(applications);
      setCounts({
        discover: jobs.length,
        score: jobs.filter((j) => j.match).length,
        apply: applications.filter((a) => a.stage !== "saved").length,
        track: applications.filter((a) =>
          ["screening", "round_1", "round_2", "final"].includes(a.stage)).length,
        schedule: 0,
        practice: 0,
      });
    };
    load();
    window.addEventListener("jcc:refresh", load);
    return () => window.removeEventListener("jcc:refresh", load);
  }, []);

  return (
    <div className="flex h-dvh flex-col">
      <Suspense fallback={<div className="h-14 border-b border-neutral-800" />}>
        <LoopSpine counts={counts} />
      </Suspense>
      <div className="flex min-h-0 flex-1">
        <VoiceRail />
        <main className="min-w-0 flex-1 overflow-y-auto p-6">{children}</main>
        <PipelineRail applications={apps} />
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Verify the shell renders**

Move the generated `app/page.tsx` to `app/(shell)/page.tsx`. Run `npm run dev`.
Expected: three columns with the spine on top, all rails visible, no horizontal scroll at 1440px wide.

- [ ] **Step 6: Commit**

```bash
git add frontend/app frontend/components
git commit -m "feat: persistent shell with voice rail, loop spine, pipeline rail"
```

---

### Task 1.9: Job card and work-surface states

**Files:**
- Create: `frontend/components/job-card.tsx`, `frontend/components/dropzone.tsx`, `frontend/components/work-surface.tsx`
- Modify: `frontend/app/(shell)/page.tsx`

**Interfaces:**
- Produces: `<JobCard job={Job} />`, `<Dropzone onUploaded={(jobs) => void} />`, `<WorkSurface state="empty"|"loading"|"loaded" jobs={Job[]} />`

Empty state and skeletons are above the cut line (Global Constraints). Build them here, not in polish.

- [ ] **Step 1: Write `frontend/components/job-card.tsx`**

```tsx
"use client";

import { motion } from "framer-motion";
import { AlertTriangle, Check, ExternalLink } from "lucide-react";
import type { Job } from "@/lib/types";

export function JobCard({ job }: { job: Job }) {
  const m = job.match;
  return (
    <motion.article
      layoutId={`job-${job.id}`}
      className="rounded-xl border border-neutral-800 bg-neutral-900 p-4"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="truncate font-medium">{job.title}</h3>
          <p className="truncate text-sm text-neutral-500">
            {job.company} · {job.location}
          </p>
        </div>
        {m && (
          <div className="shrink-0 rounded-full border border-neutral-700 px-3 py-1 font-mono text-sm tabular-nums">
            {m.score}
          </div>
        )}
      </div>

      {m && (
        <>
          <p className="mt-3 text-sm text-neutral-400">{m.rationale}</p>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {m.matched_skills.map((s) => (
              <span key={s} className="inline-flex items-center gap-1 rounded-md bg-emerald-950 px-2 py-0.5 text-xs text-emerald-300">
                <Check className="h-3 w-3" aria-hidden="true" />{s}
              </span>
            ))}
            {m.gaps.map((g) => (
              <span key={g} className="inline-flex items-center gap-1 rounded-md bg-amber-950 px-2 py-0.5 text-xs text-amber-300">
                <AlertTriangle className="h-3 w-3" aria-hidden="true" />{g}
              </span>
            ))}
          </div>
        </>
      )}

      <a
        href={job.apply_url}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-4 inline-flex items-center gap-1.5 rounded-md bg-neutral-100 px-3 py-1.5 text-sm font-medium text-neutral-900 hover:bg-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-400"
      >
        Open <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
      </a>
    </motion.article>
  );
}
```

- [ ] **Step 2: Write `frontend/components/dropzone.tsx`**

```tsx
"use client";

import { Upload } from "lucide-react";
import { useState } from "react";
import { uploadResume } from "@/lib/api";
import type { Job } from "@/lib/types";

export function Dropzone({ onUploaded }: { onUploaded: (jobs: Job[]) => void }) {
  const [error, setError] = useState<string | null>(null);

  const handle = async (file: File | undefined) => {
    if (!file) return;
    setError(null);
    try {
      const { jobs } = await uploadResume(file);
      onUploaded(jobs);
      window.dispatchEvent(new Event("jcc:refresh"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    }
  };

  return (
    <div className="grid h-full place-items-center">
      <label
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); handle(e.dataTransfer.files[0]); }}
        className="flex w-full max-w-xl cursor-pointer flex-col items-center gap-3 rounded-2xl border-2 border-dashed border-neutral-700 p-16 text-center hover:border-neutral-500"
      >
        <Upload className="h-8 w-8 text-neutral-500" aria-hidden="true" />
        <span className="text-lg font-medium">Drop your resume</span>
        <span className="text-sm text-neutral-500">
          PDF. Matching jobs are fetched and scored automatically.
        </span>
        <input
          type="file"
          accept="application/pdf"
          className="sr-only"
          onChange={(e) => handle(e.target.files?.[0])}
        />
      </label>
      {error && <p role="alert" className="mt-4 text-sm text-red-400">{error}</p>}
    </div>
  );
}
```

- [ ] **Step 3: Write `frontend/components/work-surface.tsx`**

```tsx
"use client";

import { JobCard } from "./job-card";
import type { Job } from "@/lib/types";

export function WorkSurface({
  state, jobs, children,
}: {
  state: "empty" | "loading" | "loaded";
  jobs: Job[];
  children?: React.ReactNode;
}) {
  if (state === "empty") return <>{children}</>;

  if (state === "loading") {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-40 animate-pulse rounded-xl bg-neutral-900" />
        ))}
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-3">
      {jobs.map((j) => <JobCard key={j.id} job={j} />)}
    </div>
  );
}
```

- [ ] **Step 4: Write `frontend/app/(shell)/page.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { Dropzone } from "@/components/dropzone";
import { WorkSurface } from "@/components/work-surface";
import { fetchJobs } from "@/lib/api";
import type { Job } from "@/lib/types";

export default function FeedPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [state, setState] = useState<"empty" | "loading" | "loaded">("loading");

  useEffect(() => {
    const load = () =>
      fetchJobs().then(({ jobs }) => {
        setJobs(jobs);
        setState(jobs.length ? "loaded" : "empty");
      });
    load();
    window.addEventListener("jcc:refresh", load);
    return () => window.removeEventListener("jcc:refresh", load);
  }, []);

  return (
    <WorkSurface state={state} jobs={jobs}>
      <Dropzone onUploaded={(j) => { setJobs(j); setState("loaded"); }} />
    </WorkSurface>
  );
}
```

- [ ] **Step 5: Verify the whole path by hand**

With both servers running, drop a real resume PDF on the page.
Expected: skeletons appear, then scored cards with score, matched-skill chips, gap chips, and a working Open link. Cold start (`Ctrl+R`) re-renders the same cards from `last_fetch`.

- [ ] **Step 6: Commit**

```bash
git add frontend/components frontend/app
git commit -m "feat: job cards and work-surface empty/loading/loaded states"
```

---

### Task 1.10: Data-channel event bridge

**Files:**
- Create: `frontend/lib/events.ts`, `frontend/components/event-bridge.tsx`
- Create: `backend/core/events.py`
- Modify: `frontend/app/(shell)/layout.tsx`
- Test: `backend/tests/test_events.py`

**Interfaces:**
- Produces:
  - Python `core.events.encode(type: str, payload: dict) -> bytes`
  - TypeScript `useJccEvents()` — subscribes to the room data channel, dispatches `jcc:refresh`, and routes on `navigate`

- [ ] **Step 1: Write the failing Python test**

```python
# backend/tests/test_events.py
import json
from core.events import encode, EVENT_TYPES


def test_encode_produces_utf8_json_with_type_and_payload():
    raw = encode("jobs.updated", {"count": 3})
    assert json.loads(raw.decode()) == {"type": "jobs.updated", "payload": {"count": 3}}


def test_encode_rejects_unknown_event_type():
    try:
        encode("not.a.real.event", {})
    except ValueError as e:
        assert "not.a.real.event" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_every_spec_event_type_is_registered():
    assert EVENT_TYPES == {
        "jobs.updated", "scores.updated", "application.moved",
        "interview.scheduled", "mode.changed", "navigate",
    }
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_events.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.events'`

- [ ] **Step 3: Write `backend/core/events.py`**

```python
import json

EVENT_TYPES = {
    "jobs.updated", "scores.updated", "application.moved",
    "interview.scheduled", "mode.changed", "navigate",
}


def encode(type: str, payload: dict) -> bytes:
    if type not in EVENT_TYPES:
        raise ValueError(f"Unknown event type: {type}")
    return json.dumps({"type": type, "payload": payload}).encode("utf-8")
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_events.py -v`
Expected: 3 passed

- [ ] **Step 5: Write `frontend/lib/events.ts`**

```typescript
export type JccEvent =
  | { type: "jobs.updated"; payload: { count: number } }
  | { type: "scores.updated"; payload: { count: number } }
  | { type: "application.moved"; payload: { job_id: number; stage: string } }
  | { type: "interview.scheduled"; payload: { job_id: number; when: string } }
  | { type: "mode.changed"; payload: { mode: string } }
  | { type: "navigate"; payload: { path: string } };

export function decode(data: Uint8Array): JccEvent | null {
  try {
    return JSON.parse(new TextDecoder().decode(data)) as JccEvent;
  } catch {
    return null;
  }
}
```

- [ ] **Step 6: Write `frontend/components/event-bridge.tsx`**

```tsx
"use client";

import { useDataChannel } from "@livekit/components-react";
import { useRouter } from "next/navigation";
import { decode } from "@/lib/events";

export function EventBridge() {
  const router = useRouter();

  useDataChannel((msg) => {
    const evt = decode(msg.payload);
    if (!evt) return;
    if (evt.type === "navigate") {
      router.push(evt.payload.path);
      return;
    }
    window.dispatchEvent(new Event("jcc:refresh"));
  });

  return null;
}
```

- [ ] **Step 7: Mount it in the shell layout**

In `frontend/app/(shell)/layout.tsx`, import `EventBridge` and render `<EventBridge />` as the first child of the outer `div`.

- [ ] **Step 8: Commit**

```bash
git add backend/core/events.py backend/tests/test_events.py frontend/lib/events.ts frontend/components/event-bridge.tsx frontend/app
git commit -m "feat: data-channel event bridge between agent and dashboard"
```

---

### Task 1.11: Co-pilot persona and discovery tools

**Files:**
- Create: `backend/agent/tools.py`, `backend/agent/personas.py`, `backend/agent/worker.py`
- Delete: `backend/agent/spike.py`
- Test: `backend/tests/test_tools.py`

**Interfaces:**
- Consumes: every `core` module, `core.events.encode`
- Produces: `CoPilot` agent class; module-level helpers `do_fetch_for_profile(conn)`, `do_search(conn, query, location)`, `do_explain(conn, job_id) -> str` — the pure logic behind the tools, tested without LiveKit.

Tools are thin wrappers; the testable logic lives in plain functions.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_tools.py
import pytest
from core.db import connect, init_db
from core.profile import save_profile
from agent import tools


def _conn(tmp_path):
    c = connect(str(tmp_path / "t.db"))
    init_db(c)
    save_profile(c, {"full_name": "T", "email": "", "years_experience": 4,
                     "seniority": "mid", "skills": ["Python"],
                     "titles": ["Backend Engineer"], "locations": ["Chennai"]},
                 raw_text="r")
    return c


def test_do_explain_reports_score_and_gaps(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    cur = conn.execute(
        "INSERT INTO job (source, source_id, title, company, location, apply_url) "
        "VALUES ('seed','s1','Backend Engineer','Freshworks','Chennai','u')")
    jid = cur.lastrowid
    conn.execute(
        """INSERT INTO match (job_id, profile_id, score, matched_skills_json,
             gaps_json, rationale, scored_at)
           VALUES (?,1,82,'["Python"]','["No Kubernetes experience listed"]','Fits.','now')""",
        (jid,))
    conn.commit()

    said = tools.do_explain(conn, jid)
    assert "82" in said
    assert "Python" in said
    assert "Kubernetes" in said


def test_do_explain_is_explicit_when_unscored(tmp_path):
    conn = _conn(tmp_path)
    cur = conn.execute(
        "INSERT INTO job (source, source_id, title, company, location, apply_url) "
        "VALUES ('seed','s2','Dev','Co','Chennai','u')")
    conn.commit()
    assert "not been scored" in tools.do_explain(conn, cur.lastrowid)


def test_do_explain_handles_missing_job(tmp_path):
    assert "could not find" in tools.do_explain(_conn(tmp_path), 9999).lower()


def test_do_search_scores_what_it_fetches(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    monkeypatch.setattr(tools, "fetch_jobs", lambda c, w, l: [
        {"id": 1, "title": "X", "company": "Y", "location": l}])
    called = {}
    monkeypatch.setattr(tools, "score_jobs",
                        lambda c, ids: called.setdefault("ids", ids))
    tools.do_search(conn, "backend", "Chennai")
    assert called["ids"] == [1]
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent.tools'`

- [ ] **Step 3: Write `backend/agent/tools.py`**

```python
import json

from core.jobs import fetch_jobs, query_from_profile
from core.profile import get_profile
from core.scoring import get_matches, score_jobs


def do_fetch_for_profile(conn) -> list[dict]:
    profile = get_profile(conn)
    if profile is None:
        return []
    what, where = query_from_profile(profile)
    return do_search(conn, what, where)


def do_search(conn, query: str, location: str) -> list[dict]:
    jobs = fetch_jobs(conn, query, location)
    if jobs:
        score_jobs(conn, [j["id"] for j in jobs])
    return jobs


def do_explain(conn, job_id: int) -> str:
    job = conn.execute("SELECT * FROM job WHERE id=?", (job_id,)).fetchone()
    if job is None:
        return f"I could not find a job with id {job_id}."
    m = get_matches(conn, [job_id]).get(job_id)
    if m is None:
        return f"{job['title']} at {job['company']} has not been scored yet."
    matched = ", ".join(m["matched_skills"]) or "nothing specific"
    gaps = "; ".join(m["gaps"]) or "no clear gaps"
    return (f"{job['title']} at {job['company']} scores {m['score']}. "
            f"You match on {matched}. Gaps: {gaps}. {m['rationale']}")
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_tools.py -v`
Expected: 4 passed

- [ ] **Step 5: Write `backend/agent/personas.py`**

Adjust the realtime class path to what Task 0.6 recorded. If Tripwire A fired, swap the `llm=` argument for the STT/LLM/TTS trio as described there.

```python
import os

from livekit.agents import Agent, function_tool, RunContext

from core.db import connect, init_db
from core.events import encode
from agent import tools

CO_PILOT_INSTRUCTIONS = (
    "You are the co-pilot for a job search command center. Be brief and "
    "concrete — one or two sentences per turn. When the user asks for jobs, "
    "call a tool rather than describing what you would do. Never invent a "
    "score, a company, or a job you have not fetched. After a tool runs, say "
    "what changed on screen in one sentence."
)


class CoPilot(Agent):
    def __init__(self, room):
        super().__init__(instructions=CO_PILOT_INSTRUCTIONS)
        self._room = room
        self._conn = connect()
        init_db(self._conn)

    async def _publish(self, type: str, payload: dict) -> None:
        await self._room.local_participant.publish_data(
            encode(type, payload), reliable=True
        )

    @function_tool()
    async def fetch_jobs_for_profile(self, ctx: RunContext) -> str:
        """Fetch and score jobs matching the stored resume profile."""
        jobs = tools.do_fetch_for_profile(self._conn)
        await self._publish("jobs.updated", {"count": len(jobs)})
        if not jobs:
            return "No profile is stored yet — ask the user to drop their resume."
        return f"Fetched and scored {len(jobs)} jobs."

    @function_tool()
    async def search_jobs(self, ctx: RunContext, query: str,
                          location: str = "Chennai") -> str:
        """Search live job listings for a role in a location, then score them."""
        jobs = tools.do_search(self._conn, query, location)
        await self._publish("jobs.updated", {"count": len(jobs)})
        return f"Found {len(jobs)} jobs for {query} in {location}."

    @function_tool()
    async def explain_match(self, ctx: RunContext, job_id: int) -> str:
        """Explain the score, matched skills, and gaps for one job."""
        return tools.do_explain(self._conn, job_id)
```

- [ ] **Step 6: Write `backend/agent/worker.py`**

```python
import os

from dotenv import load_dotenv
from livekit.agents import AgentSession, JobContext, WorkerOptions, cli
from livekit.plugins import google

from agent.personas import CoPilot

load_dotenv()


async def entrypoint(ctx: JobContext):
    await ctx.connect()
    session = AgentSession(
        llm=google.beta.realtime.RealtimeModel(
            model=os.environ["GEMINI_LIVE_MODEL"],
            vertexai=True,
            project=os.environ["GCP_PROJECT_ID"],
            location=os.environ["GCP_LOCATION"],
        )
    )
    await session.start(agent=CoPilot(ctx.room), room=ctx.room)
    await session.generate_reply(
        instructions="Greet the user in one sentence and offer to find jobs."
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
```

- [ ] **Step 7: Delete the spike and verify end to end**

```bash
rm backend/agent/spike.py
```

Run all three processes. In the browser, say "show me backend jobs in Chennai."
Expected: the agent calls `search_jobs`, the feed re-renders with new scored cards while the agent is still speaking, and the spine's Discover count updates.

- [ ] **Step 8: Commit**

```bash
git add backend/agent frontend backend/tests/test_tools.py
git rm --cached backend/agent/spike.py
git commit -m "feat: co-pilot persona with discovery and explain tools"
```

---

### ⛔ TRIPWIRE C — 22:00 Saturday

**Test:** does speaking "show me backend jobs in Chennai" change the feed on screen?

- **Yes** → Phase 2 proceeds in full.
- **No** → apply cut-line items 1 and 2 now, before Sunday:
  - **Task 2.7 shrinks:** the mock interviewer asks three questions built from the JD by string template, not by Gemini, and returns a fixed feedback shape.
  - **Task 2.6 shrinks:** `schedule_interview` writes the `interview` row and publishes `interview.scheduled` but makes no Calendar call. Drop the MCP wiring.

Record which cuts fired in `docs/verified-versions.md`.

---

# Phase 2 — Sunday: actions, retrieval, then ship

### Task 2.1: Application tracker

**Files:**
- Create: `backend/core/tracker.py`
- Test: `backend/tests/test_tracker.py`

**Interfaces:**
- Produces:
  - `STAGES: list[str]`
  - `save_job(conn, job_id: int) -> dict`
  - `mark_applied(conn, job_id: int) -> dict`
  - `advance_stage(conn, job_id: int, stage: str) -> dict`
  - `pipeline_summary(conn) -> str`
  - `list_applications(conn, stage: str | None = None) -> list[dict]` — accepts the pseudo-stage `interviewing`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_tracker.py
import pytest
from core.db import connect, init_db
from core import tracker


def _conn(tmp_path):
    c = connect(str(tmp_path / "t.db"))
    init_db(c)
    for i in range(3):
        c.execute("INSERT INTO job (source, source_id, title, company, location, "
                  "apply_url) VALUES ('seed',?,?,'Co','Chennai','u')",
                  (f"s{i}", f"Job {i}"))
    c.commit()
    return c


def test_mark_applied_creates_application_at_applied(tmp_path):
    conn = _conn(tmp_path)
    app = tracker.mark_applied(conn, 1)
    assert app["stage"] == "applied"
    assert app["applied_at"] is not None


def test_mark_applied_is_idempotent(tmp_path):
    conn = _conn(tmp_path)
    tracker.mark_applied(conn, 1)
    tracker.mark_applied(conn, 1)
    assert conn.execute("SELECT COUNT(*) FROM application").fetchone()[0] == 1


def test_save_job_parks_at_saved_without_applied_at(tmp_path):
    conn = _conn(tmp_path)
    app = tracker.save_job(conn, 2)
    assert app["stage"] == "saved"
    assert app["applied_at"] is None


def test_advance_stage_moves_and_stamps_updated_at(tmp_path):
    conn = _conn(tmp_path)
    tracker.mark_applied(conn, 1)
    app = tracker.advance_stage(conn, 1, "round_1")
    assert app["stage"] == "round_1"
    assert app["updated_at"] is not None


def test_advance_stage_rejects_unknown_stage(tmp_path):
    conn = _conn(tmp_path)
    tracker.mark_applied(conn, 1)
    with pytest.raises(ValueError, match="Unknown stage"):
        tracker.advance_stage(conn, 1, "interviewed_maybe")


def test_advance_stage_rejects_untracked_job(tmp_path):
    with pytest.raises(ValueError, match="not tracked"):
        tracker.advance_stage(_conn(tmp_path), 3, "round_1")


def test_list_applications_expands_the_interviewing_pseudo_stage(tmp_path):
    conn = _conn(tmp_path)
    tracker.mark_applied(conn, 1)
    tracker.advance_stage(conn, 1, "round_2")
    tracker.mark_applied(conn, 2)
    assert [a["job_id"] for a in tracker.list_applications(conn, "interviewing")] == [1]


def test_pipeline_summary_counts_by_stage(tmp_path):
    conn = _conn(tmp_path)
    tracker.mark_applied(conn, 1)
    tracker.mark_applied(conn, 2)
    tracker.advance_stage(conn, 2, "round_1")
    s = tracker.pipeline_summary(conn)
    assert "1 applied" in s and "1 round 1" in s


def test_pipeline_summary_handles_empty_pipeline(tmp_path):
    assert "nothing" in tracker.pipeline_summary(_conn(tmp_path)).lower()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_tracker.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.tracker'`

- [ ] **Step 3: Write `backend/core/tracker.py`**

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_tracker.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add backend/core/tracker.py backend/tests/test_tracker.py
git commit -m "feat: application tracker with stage machine"
```

---

### Task 2.2: Retrieval — `find_jobs`

**Files:**
- Create: `backend/core/search.py`
- Test: `backend/tests/test_search.py`

**Interfaces:**
- Produces: `find_jobs(conn, query: str) -> list[dict]` — matches company, title, or a stage name across stored jobs, returning job rows with `match` and `stage` attached.

If Tripwire B fired, skip this task.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_search.py
from core.db import connect, init_db
from core import search, tracker


def _conn(tmp_path):
    c = connect(str(tmp_path / "t.db"))
    init_db(c)
    c.execute("INSERT INTO job (source, source_id, title, company, location, "
              "apply_url) VALUES ('seed','s1','Backend Engineer','Freshworks','Chennai','u')")
    c.execute("INSERT INTO job (source, source_id, title, company, location, "
              "apply_url) VALUES ('seed','s2','Data Analyst','Zoho','Chennai','u')")
    c.commit()
    return c


def test_find_jobs_matches_company_case_insensitively(tmp_path):
    r = search.find_jobs(_conn(tmp_path), "freshworks")
    assert [j["company"] for j in r] == ["Freshworks"]


def test_find_jobs_matches_title_substring(tmp_path):
    r = search.find_jobs(_conn(tmp_path), "analyst")
    assert [j["title"] for j in r] == ["Data Analyst"]


def test_find_jobs_matches_a_stage_name(tmp_path):
    conn = _conn(tmp_path)
    tracker.mark_applied(conn, 1)
    tracker.advance_stage(conn, 1, "round_2")
    r = search.find_jobs(conn, "round 2")
    assert [j["id"] for j in r] == [1]


def test_find_jobs_attaches_stage_when_tracked(tmp_path):
    conn = _conn(tmp_path)
    tracker.mark_applied(conn, 1)
    assert search.find_jobs(conn, "freshworks")[0]["stage"] == "applied"


def test_find_jobs_returns_empty_for_no_match(tmp_path):
    assert search.find_jobs(_conn(tmp_path), "quantum welder") == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_search.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.search'`

- [ ] **Step 3: Write `backend/core/search.py`**

```python
from core.scoring import get_matches
from core.tracker import STAGES


def find_jobs(conn, query: str) -> list[dict]:
    q = (query or "").strip().lower()
    if not q:
        return []

    stage = next((s for s in STAGES if s.replace("_", " ") == q or s == q), None)
    if stage:
        rows = conn.execute(
            """SELECT j.*, a.stage FROM job j
               JOIN application a ON a.job_id = j.id WHERE a.stage=?""", (stage,))
    else:
        like = f"%{q}%"
        rows = conn.execute(
            """SELECT j.*, a.stage FROM job j
               LEFT JOIN application a ON a.job_id = j.id
               WHERE LOWER(j.company) LIKE ? OR LOWER(j.title) LIKE ?""",
            (like, like))

    jobs = [dict(r) for r in rows]
    matches = get_matches(conn, [j["id"] for j in jobs])
    return [{**j, "match": matches.get(j["id"])} for j in jobs]
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_search.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/core/search.py backend/tests/test_search.py
git commit -m "feat: retrieval over stored jobs and applications"
```

---

### Task 2.3: Action tools and API routes

**Files:**
- Modify: `backend/agent/personas.py`, `backend/api/main.py`
- Test: `backend/tests/test_api_actions.py`

**Interfaces:**
- Produces:
  - Tools on `CoPilot`: `save_job`, `mark_applied`, `advance_stage`, `pipeline_status`, `find_jobs`
  - Endpoints: `POST /api/applications/{job_id}/apply`, `POST /api/applications/{job_id}/stage`, `GET /api/search?q=`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_api_actions.py
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("LIVEKIT_API_KEY", "devkey")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "devsecretdevsecretdevsecret")
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")
    from api.main import create_app
    from core.db import connect
    app = create_app()
    c = connect(str(tmp_path / "t.db"))
    c.execute("INSERT INTO job (source, source_id, title, company, location, "
              "apply_url) VALUES ('seed','s1','Backend Engineer','Freshworks','Chennai','u')")
    c.commit()
    return TestClient(app)


def test_apply_endpoint_moves_job_to_applied(client):
    r = client.post("/api/applications/1/apply")
    assert r.status_code == 200
    assert r.json()["application"]["stage"] == "applied"
    assert any(a["stage"] == "applied"
               for a in client.get("/api/applications").json()["applications"])


def test_stage_endpoint_rejects_unknown_stage(client):
    client.post("/api/applications/1/apply")
    r = client.post("/api/applications/1/stage", json={"stage": "nope"})
    assert r.status_code == 400


def test_search_endpoint_finds_by_company(client):
    r = client.get("/api/search", params={"q": "freshworks"})
    assert [j["company"] for j in r.json()["jobs"]] == ["Freshworks"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_api_actions.py -v`
Expected: FAIL — 404 on the new routes

- [ ] **Step 3: Add the routes to `backend/api/main.py`**

Add these imports at the top:

```python
from fastapi import Body
from core.search import find_jobs as _find_jobs
from core import tracker
```

Add these routes inside `create_app`, before `return app`:

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_api_actions.py -v`
Expected: 3 passed

- [ ] **Step 5: Add the tools to `backend/agent/personas.py`**

Add to the top: `from core import search as core_search, tracker`

Add these methods to `CoPilot`:

```python
    @function_tool()
    async def save_job(self, ctx: RunContext, job_id: int) -> str:
        """Save a job for later without applying to it."""
        app = tracker.save_job(self._conn, job_id)
        await self._publish("application.moved",
                            {"job_id": job_id, "stage": app["stage"]})
        return f"Saved job {job_id}."

    @function_tool()
    async def mark_applied(self, ctx: RunContext, job_id: int) -> str:
        """Mark a job as applied. Does NOT open the posting — the user clicks Open."""
        app = tracker.mark_applied(self._conn, job_id)
        await self._publish("application.moved",
                            {"job_id": job_id, "stage": app["stage"]})
        return ("Marked as applied. The Open button on that card is ready "
                "whenever you want the posting.")

    @function_tool()
    async def advance_stage(self, ctx: RunContext, job_id: int, stage: str) -> str:
        """Move an application to a new stage, e.g. screening, round_1, offer."""
        try:
            app = tracker.advance_stage(self._conn, job_id, stage)
        except ValueError as e:
            return str(e)
        await self._publish("application.moved",
                            {"job_id": job_id, "stage": app["stage"]})
        return f"Moved job {job_id} to {stage.replace('_', ' ')}."

    @function_tool()
    async def pipeline_status(self, ctx: RunContext) -> str:
        """Summarise every application in the pipeline."""
        return tracker.pipeline_summary(self._conn)

    @function_tool()
    async def find_jobs(self, ctx: RunContext, query: str) -> str:
        """Retrieve previously seen jobs by company, title, or stage."""
        found = core_search.find_jobs(self._conn, query)
        await self._publish("navigate", {"path": f"/search?q={query}"})
        if not found:
            return f"I found nothing matching {query}."
        head = ", ".join(f"{j['title']} at {j['company']}" for j in found[:3])
        return f"Found {len(found)}. {head}."
```

- [ ] **Step 6: Commit**

```bash
git add backend/api/main.py backend/agent/personas.py backend/tests/test_api_actions.py
git commit -m "feat: apply, stage, and retrieval tools and endpoints"
```

---

### Task 2.4: Apply split and armed Open button

**Files:**
- Modify: `frontend/components/job-card.tsx`
- Create: `frontend/app/(shell)/pipeline/page.tsx`, `frontend/app/(shell)/search/page.tsx`

**Interfaces:**
- Consumes: `POST /api/applications/{job_id}/apply`, `GET /api/search`, `GET /api/applications`

Voice marks state; the click opens the URL (Global Constraints).

- [ ] **Step 1: Add the applied/armed state to `JobCard`**

Replace the `<a>` block in `job-card.tsx` with:

```tsx
      <div className="mt-4 flex items-center gap-2">
        {!applied && (
          <button
            onClick={async () => {
              await fetch(`${process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000"}/api/applications/${job.id}/apply`, { method: "POST" });
              setApplied(true);
              window.dispatchEvent(new Event("jcc:refresh"));
            }}
            className="rounded-md border border-neutral-700 px-3 py-1.5 text-sm hover:bg-neutral-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-400"
          >
            Mark applied
          </button>
        )}
        <a
          href={job.apply_url}
          target="_blank"
          rel="noopener noreferrer"
          className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-400 ${
            applied
              ? "animate-pulse bg-emerald-400 text-neutral-900"
              : "bg-neutral-100 text-neutral-900 hover:bg-white"
          }`}
        >
          Open <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
        </a>
      </div>
```

Add to the top of the component body:

```tsx
  const [applied, setApplied] = useState(job.stage === "applied");
```

and add `useState` to the React import, plus `stage?: string` to the `Job` type in `lib/types.ts`.

- [ ] **Step 2: Write `frontend/app/(shell)/pipeline/page.tsx`**

```tsx
"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { fetchApplications } from "@/lib/api";
import type { Application } from "@/lib/types";

const INTERVIEWING = ["screening", "round_1", "round_2", "final"];

export default function PipelinePage() {
  const stage = useSearchParams().get("stage") ?? "applied";
  const [apps, setApps] = useState<Application[]>([]);

  useEffect(() => {
    const load = () => fetchApplications().then(({ applications }) => {
      setApps(applications.filter((a) =>
        stage === "interviewing" ? INTERVIEWING.includes(a.stage) : a.stage === stage));
    });
    load();
    window.addEventListener("jcc:refresh", load);
    return () => window.removeEventListener("jcc:refresh", load);
  }, [stage]);

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-4 text-sm uppercase tracking-wide text-neutral-500">
        {stage.replace("_", " ")} · {apps.length}
      </h1>
      {apps.length === 0 && <p className="text-neutral-600">Nothing at this stage yet.</p>}
      <ul className="flex flex-col gap-2">
        {apps.map((a) => (
          <li key={a.id} className="rounded-xl border border-neutral-800 bg-neutral-900 p-4">
            <div className="font-medium">{a.title}</div>
            <div className="text-sm text-neutral-500">{a.company}</div>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 3: Write `frontend/app/(shell)/search/page.tsx`**

```tsx
"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { JobCard } from "@/components/job-card";
import type { Job } from "@/lib/types";

export default function SearchPage() {
  const q = useSearchParams().get("q") ?? "";
  const [jobs, setJobs] = useState<Job[]>([]);

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
    fetch(`${base}/api/search?q=${encodeURIComponent(q)}`)
      .then((r) => r.json())
      .then((d) => setJobs(d.jobs));
  }, [q]);

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-sm uppercase tracking-wide text-neutral-500">
          “{q}” · {jobs.length}
        </h1>
        <Link href="/" className="text-sm text-neutral-400 hover:text-neutral-200">
          Back to feed
        </Link>
      </div>
      {jobs.length === 0 && <p className="text-neutral-600">Nothing matched.</p>}
      <div className="flex flex-col gap-3">
        {jobs.map((j) => <JobCard key={j.id} job={j} />)}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Verify by voice**

Say "apply to job 1", then "what did I apply to at Freshworks".
Expected: the card flips to applied with a pulsing Open button, the pipeline rail gains an entry, and the second command routes to `/search?q=...`.

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "feat: apply split, pipeline route, and search route"
```

---

### Task 2.5: Interview scheduling

**Files:**
- Modify: `backend/agent/personas.py`, `backend/agent/worker.py`
- Create: `backend/core/interviews.py`
- Test: `backend/tests/test_interviews.py`

**Interfaces:**
- Produces: `record_interview(conn, job_id: int, when: str, round_label: str, calendar_event_id: str | None) -> dict`, `upcoming(conn) -> list[dict]`

If Tripwire C fired, implement only the local row and skip the MCP wiring in Step 5.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_interviews.py
import pytest
from core.db import connect, init_db
from core import interviews, tracker


def _conn(tmp_path):
    c = connect(str(tmp_path / "t.db"))
    init_db(c)
    c.execute("INSERT INTO job (source, source_id, title, company, location, "
              "apply_url) VALUES ('seed','s1','Backend Engineer','Freshworks','Chennai','u')")
    c.commit()
    tracker.mark_applied(c, 1)
    return c


def test_record_interview_links_to_the_application(tmp_path):
    conn = _conn(tmp_path)
    iv = interviews.record_interview(conn, 1, "2026-08-18T15:00:00", "round_1", "evt-1")
    assert iv["round_label"] == "round_1"
    assert iv["calendar_event_id"] == "evt-1"


def test_record_interview_requires_a_tracked_job(tmp_path):
    conn = _conn(tmp_path)
    with pytest.raises(ValueError, match="not tracked"):
        interviews.record_interview(conn, 999, "2026-08-18T15:00:00", "round_1", None)


def test_upcoming_lists_future_interviews_with_job_details(tmp_path):
    conn = _conn(tmp_path)
    interviews.record_interview(conn, 1, "2099-01-01T10:00:00", "round_1", None)
    up = interviews.upcoming(conn)
    assert up[0]["company"] == "Freshworks"


def test_upcoming_excludes_past_interviews(tmp_path):
    conn = _conn(tmp_path)
    interviews.record_interview(conn, 1, "2020-01-01T10:00:00", "round_1", None)
    assert interviews.upcoming(conn) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_interviews.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.interviews'`

- [ ] **Step 3: Write `backend/core/interviews.py`**

```python
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


def upcoming(conn) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    rows = conn.execute(
        """SELECT i.*, j.title, j.company FROM interview i
           JOIN application a ON a.id = i.application_id
           JOIN job j ON j.id = a.job_id
           WHERE i.scheduled_at > ? ORDER BY i.scheduled_at""", (now,))
    return [dict(r) for r in rows]
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_interviews.py -v`
Expected: 4 passed

- [ ] **Step 5: Attach the Workspace MCP server to the agent**

In `backend/agent/worker.py`, add the MCP server to the session. Verify the correct import path first:

```bash
.venv/Scripts/python -c "from livekit.agents import mcp; print([n for n in dir(mcp) if not n.startswith('_')])"
```

Then add to `AgentSession(...)`:

```python
        mcp_servers=[mcp.MCPServerStdio(
            command="uvx",
            args=["workspace-mcp"],
        )],
```

Replace `command`/`args` with however the Workspace MCP server is launched on this machine. If it fails to attach, fall back per spec §11: call the Calendar REST API directly with the same credentials.

- [ ] **Step 6: Add the tool to `CoPilot`**

```python
    @function_tool()
    async def schedule_interview(self, ctx: RunContext, job_id: int,
                                 when: str, round_label: str = "round_1") -> str:
        """Schedule an interview. `when` must be an ISO 8601 datetime."""
        from core.interviews import record_interview
        iv = record_interview(self._conn, job_id, when, round_label, None)
        await self._publish("interview.scheduled", {"job_id": job_id, "when": when})
        return (f"Scheduled {round_label.replace('_', ' ')} for job {job_id} "
                f"at {when}. Interview id {iv['id']}.")
```

The agent creates the Calendar event by calling the MCP server's own tool in the same turn; this tool records the local row.

- [ ] **Step 7: Commit**

```bash
git add backend/core/interviews.py backend/tests/test_interviews.py backend/agent
git commit -m "feat: interview scheduling with Workspace MCP"
```

---

### Task 2.6: Mock interviewer persona

**Files:**
- Modify: `backend/agent/personas.py`
- Create: `backend/core/mock.py`, `frontend/app/(focus)/practice/[jobId]/page.tsx`
- Test: `backend/tests/test_mock.py`

**Interfaces:**
- Produces: `build_questions(conn, job_id: int) -> list[str]`, `save_session(conn, job_id, transcript, feedback) -> int`, `MockInterviewer` agent class

If Tripwire C fired, `build_questions` uses the template path only — skip the Gemini branch.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_mock.py
from core.db import connect, init_db
from core import mock


def _conn(tmp_path):
    c = connect(str(tmp_path / "t.db"))
    init_db(c)
    c.execute("INSERT INTO job (source, source_id, title, company, location, "
              "description, apply_url) VALUES ('seed','s1','Backend Engineer',"
              "'Freshworks','Chennai','Django, PostgreSQL, Kubernetes.','u')")
    c.execute("""INSERT INTO match (job_id, profile_id, score, matched_skills_json,
                 gaps_json, rationale, scored_at)
                 VALUES (1,1,70,'["Python"]','["No Kubernetes experience listed"]','x','now')""")
    c.commit()
    return c


def test_build_questions_returns_three(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    monkeypatch.setattr(mock, "generate_json", lambda p, s, m=None: {
        "questions": ["Q1", "Q2", "Q3"]})
    assert mock.build_questions(conn, 1) == ["Q1", "Q2", "Q3"]


def test_build_questions_prompt_includes_the_gap(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    seen = {}
    monkeypatch.setattr(mock, "generate_json",
                        lambda p, s, m=None: seen.setdefault("p", p) or {"questions": ["a"]})
    mock.build_questions(conn, 1)
    assert "Kubernetes" in seen["p"]


def test_build_questions_falls_back_to_template_on_failure(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    monkeypatch.setattr(mock, "generate_json",
                        lambda p, s, m=None: (_ for _ in ()).throw(RuntimeError("down")))
    qs = mock.build_questions(conn, 1)
    assert len(qs) == 3
    assert any("Backend Engineer" in q for q in qs)


def test_save_session_persists_transcript_and_feedback(tmp_path):
    conn = _conn(tmp_path)
    sid = mock.save_session(conn, 1, "hello", {"strengths": ["clear"]})
    row = conn.execute("SELECT * FROM mock_session WHERE id=?", (sid,)).fetchone()
    assert row["transcript"] == "hello"
    assert "clear" in row["feedback_json"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_mock.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.mock'`

- [ ] **Step 3: Write `backend/core/mock.py`**

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_mock.py -v`
Expected: 4 passed

- [ ] **Step 5: Add `MockInterviewer` to `backend/agent/personas.py`**

The interviewer gets no mutation tools (spec §7).

```python
class MockInterviewer(Agent):
    def __init__(self, room, job_id: int, questions: list[str]):
        numbered = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
        super().__init__(instructions=(
            "You are conducting a mock job interview. Ask these three questions "
            "one at a time, waiting for a full answer before moving on. Do not "
            "coach mid-interview. After the third answer, give brief feedback: "
            "two strengths and two specific improvements, then call "
            "end_mock_interview.\n\n" + numbered
        ))
        self._room = room
        self._job_id = job_id

    @function_tool()
    async def end_mock_interview(self, ctx: RunContext) -> str:
        """End the mock interview and return to the dashboard."""
        await self._room.local_participant.publish_data(
            encode("navigate", {"path": "/"}), reliable=True)
        return "Interview complete."
```

Add the handoff tool to `CoPilot`:

```python
    @function_tool()
    async def start_mock_interview(self, ctx: RunContext, job_id: int) -> Agent:
        """Start a mock interview for one job. Hands off to the interviewer."""
        from core.mock import build_questions
        questions = build_questions(self._conn, job_id)
        await self._publish("navigate", {"path": f"/practice/{job_id}"})
        await self._publish("mode.changed", {"mode": "mock_interview"})
        return MockInterviewer(self._room, job_id, questions)
```

Verify that returning an `Agent` from a tool performs the handoff in your installed `livekit-agents` version:

```bash
.venv/Scripts/python -c "import livekit.agents, inspect; print(inspect.getdoc(livekit.agents.Agent))"
```

If handoff works differently, use the documented mechanism and note it in `docs/verified-versions.md`.

- [ ] **Step 6: Write `frontend/app/(focus)/practice/[jobId]/page.tsx`**

The `(focus)` group has no shell chrome, so this renders full-bleed. The LiveKit session survives because the provider is in the root layout.

```tsx
"use client";

import { useVoiceAssistant, BarVisualizer } from "@livekit/components-react";
import Link from "next/link";
import { use } from "react";

export default function PracticePage({
  params,
}: { params: Promise<{ jobId: string }> }) {
  const { jobId } = use(params);
  const { state, audioTrack } = useVoiceAssistant();

  return (
    <main className="grid h-dvh place-items-center bg-neutral-950 p-8">
      <div className="flex w-full max-w-xl flex-col items-center gap-6">
        <p className="text-sm uppercase tracking-widest text-neutral-500">
          Mock interview · job {jobId}
        </p>
        <div className="h-40 w-full rounded-2xl bg-neutral-900 p-4">
          <BarVisualizer state={state} barCount={9} trackRef={audioTrack} />
        </div>
        <p aria-live="polite" className="text-neutral-400">
          {state === "speaking" ? "Interviewer is speaking" : "Your turn"}
        </p>
        <Link href="/" className="text-sm text-neutral-500 hover:text-neutral-300">
          Exit interview
        </Link>
      </div>
    </main>
  );
}
```

- [ ] **Step 7: Verify the session survives navigation**

Say "start a mock interview for job 1."
Expected: the app routes to `/practice/1` full-bleed, the interviewer asks question one **without the voice dropping**, and "Exit interview" returns to the feed with the session still live. If the voice cuts out, the provider is in the wrong layout — check Global Constraints.

- [ ] **Step 8: Commit**

```bash
git add backend/core/mock.py backend/tests/test_mock.py backend/agent/personas.py frontend/app
git commit -m "feat: mock interviewer persona with full-bleed practice route"
```

---

### ⛔ TRIPWIRE D — 12:00 Sunday. Hard feature freeze.

Stop implementing. For every task not finished, apply the matching cut from spec §12 and delete or stub the incomplete code so nothing half-built reaches the demo. Record what was cut in `docs/verified-versions.md`. The rest of Sunday is Tasks 2.7–2.9 only.

---

### Task 2.7: Dev script and full-loop rehearsal pass

**Files:**
- Create: `scripts/dev.ps1`
- Modify: `README.md`

- [ ] **Step 1: Write `scripts/dev.ps1`**

```powershell
# Starts all three processes in separate windows.
$root = Split-Path $PSScriptRoot -Parent
Start-Process powershell -ArgumentList "-NoExit","-Command","Set-Location '$root\backend'; .venv\Scripts\python -m uvicorn api.main:app --reload --port 8000"
Start-Process powershell -ArgumentList "-NoExit","-Command","Set-Location '$root\backend'; .venv\Scripts\python -m agent.worker dev"
Start-Process powershell -ArgumentList "-NoExit","-Command","Set-Location '$root\frontend'; npm run dev"
Write-Output "Started API (8000), agent worker, and frontend (3000)."
```

- [ ] **Step 2: Run the whole loop once, start to finish**

```powershell
.\scripts\dev.ps1
```

Walk every spine stage in order and confirm each: drop resume → scored cards → "show me backend jobs in Chennai" → "apply to job N" → Open button pulses and opens → "move job N to round 1" → "schedule an interview Tuesday at 3" → "what did I apply to at Freshworks" → "start a mock interview for job N".

- [ ] **Step 3: Fix only what is broken in that path**

Anything outside the loop stays as it is. It is past the freeze.

- [ ] **Step 4: Commit**

```bash
git add scripts/dev.ps1
git commit -m "chore: single dev start script for all three processes"
```

---

### Task 2.8: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write it**

Cover, in this order: what it is in two sentences; a screenshot; the architecture diagram from spec §4; setup (Python 3.12, venv, `.env` keys, `npm install`); how to run (`scripts/dev.ps1`); the agent's tool list from spec §7; what is deliberately out of scope from spec §13; and a note that model IDs are recorded in `docs/verified-versions.md`.

Link the spec and this plan. State plainly which cut-line items fired, if any — an honest note reads better than a silent gap.

- [ ] **Step 2: Verify setup from scratch**

Re-read the setup section as if you had never seen the repo. Every command must be copy-pasteable and every env var listed.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: README with setup, architecture, and scope"
```

---

### Task 2.9: Rehearse and record

- [ ] **Step 1: Write a 4-minute script**

Beat per spine stage, timed. Roughly: 20s framing, 40s resume→scored cards, 40s voice search, 40s apply→tracker, 30s schedule, 40s retrieval, 50s mock interview, 20s close.

- [ ] **Step 2: Rehearse twice**

Run it end to end, timed, without stopping. Note anything that stalls; fix only outright breakage.

- [ ] **Step 3: Reset to a clean state**

```bash
rm backend/tracker.db backend/tracker.db-wal backend/tracker.db-shm
```

Restart via `scripts/dev.ps1` so the recording opens on the empty state.

- [ ] **Step 4: Record by 17:00**

Screen plus microphone at 1440×900 or wider. Keep the first usable take; do not chase perfection with the deadline approaching.

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: demo script and final state for submission"
```

---

## Self-Review

**Spec coverage.** Every section maps to at least one task: §3 walkthrough → 1.2, 1.4, 1.5, 2.1, 2.4, 2.5, 2.6 · §4 architecture → 1.6, 1.7, 1.11 · §5 stack → 0.2, 1.7 · §6 data model → 1.1 (all seven tables including `fetch_run`) · §7 tools → 1.11, 2.3, 2.5, 2.6, with `mark_applied`'s no-open rule enforced in 2.3 and 2.4 · §8 scoring → 1.5 · §9 UI → 1.7 (root provider), 1.8 (shell, spine, rails), 1.9 (three surface states, cold start), 2.4 (routes, apply split), 2.6 (full-bleed practice) · §10 schedule → phase structure and four tripwire gates · §11 risks → each has a task or a tripwire · §12 cut line → wired into Tripwires B, C, D · §13 out of scope → no task builds any of it.

**Two gaps I found and closed while reviewing:** card expand-in-place (spec §9) has no task — it is the lowest-value item in the approved history layer and is explicitly cut at Tripwire B, so it is listed in the cut line rather than given a task; and the spine's Schedule/Practice counts are wired to `0` in Task 1.8 because `interviews.upcoming` and `mock_session` do not exist until Phase 2 — Task 2.5 and 2.6 leave them at zero rather than backfilling, which is honest under the freeze but worth knowing.

**Type consistency.** `Job.match` is `Match | null` in `lib/types.ts` and is populated by `_decorate` in both `/api/jobs` and `/api/search`, and by `core.search.find_jobs`. `get_matches` returns `dict[int, dict]` keyed by `job_id` and is consumed identically in `api/main.py`, `agent/tools.py`, `core/search.py`, and `core/mock.py`. Stage strings come from `tracker.STAGES` in Python and the matching literal array in `pipeline-rail.tsx`; the `interviewing` pseudo-stage is expanded in exactly two places, `tracker.list_applications` and `pipeline/page.tsx`.

---

Plan complete and saved to `docs/superpowers/plans/2026-08-14-job-search-command-center.md`. Two execution options:

**1. Subagent-Driven (recommended)** — a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
