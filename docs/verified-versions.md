# Verified Versions

Recorded during Phase 0. Later tasks read values from this file rather than
guessing. Update in place if anything changes.

| What | Value | Verified |
|---|---|---|
| Python | 3.12.0 | 2026-08-14 |
| livekit-agents | 1.6.10 | 2026-08-14 |
| google-genai | 2.18.0 | 2026-08-14 |
| fastapi | 0.141.1 | 2026-08-14 |
| pypdf | 6.16.0 | 2026-08-14 |
| uvicorn | 0.52.3 | 2026-08-14 |
| pytest | 9.1.1 | 2026-08-14 |
| GCP project | `minna-501517` | 2026-08-14 |
| GCP region | `us-central1` | 2026-08-14 |
| `GEMINI_LIVE_MODEL` | `gemini-live-2.5-flash-native-audio` | 2026-08-14 |
| `GEMINI_BATCH_MODEL` | `gemini-2.5-flash` | 2026-08-14 |

## Vertex AI credentials

Reusing a **pre-existing user-managed service account** rather than creating a
new one (Task 0.3's `gcloud iam service-accounts create` steps are therefore
skipped as unnecessary):

- Identity: `memoryassistant@minna-501517.iam.gserviceaccount.com`
- Key path: `C:\project\memory-mcp-main\memory-assistant\minna-501517-74100a53d61f.json`

The key lives **outside this repository on purpose** and is referenced by
absolute path from `backend/.env`. Do not copy it into the repo — this
repository is a submission artifact handed to a third party, and a service
account private key must never travel with it, gitignored or not.

Verified working: `models.list()` returned 127 models, and a real
`generate_json` round-trip through `core/gemini.py` returned valid structured
JSON (`{'ok': True, 'note': 'vertex reachable'}`).

## Gemini model selection

`gemini-live-2.5-flash-native-audio` is the **only** live/realtime-capable
model exposed on this project — there is no alternative to fall back to if it
misbehaves, which is what Tripwire A's STT→LLM→TTS pipeline exists for.

For batch reasoning the project also exposes `gemini-3.5-flash`,
`gemini-3.6-flash`, and `gemini-3.7-flash`. The spec names 2.5 Flash and that
is what is configured. If scoring quality disappoints during Saturday testing,
`gemini-3.7-flash` is a one-env-var swap — no code change.

## LiveKit (Task 0.4)

- URL: `wss://job-command-center-u51p42wl.livekit.cloud`
- Credentials in `backend/.env` (gitignored).

Token minting verified twice: directly against the `livekit` SDK, and through
the real `/api/token` route with credentials loaded from `.env`. The issued
JWT decodes to `alg=HS256` with grants
`{roomJoin: true, room: "command-center", canPublish: true, canSubscribe: true, canPublishData: true}`.
`canPublishData` matters — the agent publishes UI events over the room data
channel, and without it the dashboard would never update.

The SDK surface matches the plan's assumption:
`api.AccessToken(key, secret).with_identity(...).with_grants(api.VideoGrants(...)).to_jwt()`.

Note: the API secret is 27 bytes, below the 32-byte minimum PyJWT recommends
for HS256; it emits an `InsecureKeyLengthWarning`. This is LiveKit Cloud's own
generated secret and is theirs to size — no action, but the warning in test
output is expected and not a defect.

## Adzuna coverage (Task 0.5)

Verified live against the India endpoint on 2026-08-14 with real credentials.
Chennai coverage is healthy, so **Adzuna stays the primary source** and
`backend/data/seed_chennai.json` remains a genuine fallback rather than the
demo's actual data source:

| Query | Total matches | Returned |
|---|---|---|
| `backend engineer` | 93 | 10 |
| `python developer` | 231 | 10 |
| `software engineer` | 1084 | 10 |

Results carry real `redirect_url` values pointing at `adzuna.in` postings,
which satisfies the spec's requirement for a genuine apply link.

## Tripwire A — voice spike (Task 0.7)

**PASSED at 2026-08-14 09:33 IST**, well ahead of the 23:00 deadline. Gemini
Live over Vertex holds a stable multi-turn spoken conversation through
LiveKit. Full transcript (via LiveKit Console, `job_id=AJ_ibpzMSDFsSdV`):

```
assistant: Hello! How can I help you today?
user:      Who are you?
assistant: I am the job search command center spike.
user:      Tell me about this project.
assistant: This project is a voice pipeline test.
user:      Who are you?
assistant: I am the job search command center spike.
```

### Bug found and fixed: default job executor crashes on Windows

The first two attempts died silently — `python.exe` exited with code 255,
zero Python traceback — every time, immediately after the log line
`"connecting to Gemini Realtime API..."`. That log line sits inside
`RealtimeSession._main_task`, which is wrapped in `@utils.log_exceptions`;
a genuine Python exception there would have printed. Its total absence
pointed away from a catchable error.

**Root cause:** `livekit-agents`' `WorkerOptions.job_executor_type` defaults
to `JobExecutorType.THREAD` — each job runs in a background thread of the
main process, each spinning up its own nested `asyncio` `ProactorEventLoop`.
A Proactor loop created inside a non-main thread is a known-fragile
combination on Windows (IOCP-level failures can kill the process below
Python's exception handling entirely, which matches the symptom exactly).

**Isolating the cause:** a standalone script calling
`client.aio.live.connect(...)` directly — same model, same credentials, same
network path, but a single `asyncio.run()` on the main thread, no
`livekit-agents` job-runner involved — connected cleanly and streamed real
audio back (five chunks, ~55KB) with no issue. This proved Vertex Live
connectivity itself was never the problem.

**Fix:** pass `job_executor_type=JobExecutorType.PROCESS` to `WorkerOptions`.
Each job then gets a genuine isolated OS process with a clean main-thread
event loop — architecturally identical to the working standalone repro.
First attempt after the fix succeeded immediately.

**This is a REQUIRED constraint on every later worker**, not just the spike.
`backend/agent/worker.py` (Task 1.11) must set
`job_executor_type=JobExecutorType.PROCESS` in its `WorkerOptions`, or it
will hit the identical silent crash the moment it tries to open a Gemini
Live session.

Secondary observation, not a blocker: job process memory climbed past the
1000MB advisory threshold to ~2GB over ~2.5 minutes of conversation
(`"job process memory usage is above the warning threshold"`, advisory only,
not terminated). Worth a glance if a mock-interview session runs long, though
the spec already caps those at 3-5 questions for an unrelated reason
(historical Gemini Live session-length limits).

## SDK surface

`google-genai` 2.18.0 matches the shape the plan assumed:
`genai.Client(vertexai=True, project=..., location=...)` and
`types.GenerateContentConfig(response_mime_type=..., response_schema=...)`.
Confirmed by the live round-trip above, not by inspection alone.
