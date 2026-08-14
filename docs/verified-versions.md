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

## SDK surface

`google-genai` 2.18.0 matches the shape the plan assumed:
`genai.Client(vertexai=True, project=..., location=...)` and
`types.GenerateContentConfig(response_mime_type=..., response_schema=...)`.
Confirmed by the live round-trip above, not by inspection alone.
