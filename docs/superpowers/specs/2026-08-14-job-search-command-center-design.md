# Job Search Command Center — Design Spec

- **Date:** 2026-08-14 (revised same day)
- **Deadline:** Sunday 2026-08-16, end of day
- **Context:** Company assessment submission
- **Status:** Revised draft, awaiting review

---

## 0. What changed in this revision

| Change | Reason |
|---|---|
| Schedule re-baselined to three buckets with timed tripwires | The original four-bucket plan ended Monday morning, past the deadline |
| Named the API server and token endpoint | The architecture had no component serving REST or minting LiveKit tokens |
| Apply split into a voice half and a click half | A tab opened from a tool call has no user activation and is suppressed by the browser |
| Voice fallback path added | Requirement #1 rested on an unproven preview API with no plan B |
| Navigation model: persistent shell with a routed center | History retrieval needs view states; hand-rolling them in React state costs more than routing |
| History layer added (`find_jobs`, saved jobs, stage views, card expansion) | Nothing in the original retrieved a listing once the feed refreshed |
| Empty state and loading skeletons promoted above the cut line | They are the demo's opening shot and its longest wait |
| Cut line reordered to remove depth, never a stage | The demo thesis is the complete loop, so every stage must survive |
| Python install added as an explicit Day 0 blocker | Verified absent on the build machine |

---

## 1. Problem

A job hunt is spread across a dozen tabs: job boards, a spreadsheet tracker, a
resume you retype for every application, a calendar you update by hand, and no
honest read on whether you are actually a fit for anything.

This builds one screen that collapses all of it, driven by voice, where an agent
does the work rather than answering questions about it.

---

## 2. Assessment requirements this must satisfy

| Requirement | How it is met |
|---|---|
| Voice-first, natural conversation | LiveKit + Gemini Live speech-to-speech, in both the dashboard co-pilot and the mock interviewer |
| Agent reasons and takes actions | Tool-calling agent that fetches, scores, applies, tracks, retrieves, and schedules |
| UI/UX is our call | Persistent command-center shell with a routed work surface |
| Heavy AI use while building | Built with Claude Code throughout |

**Voice is the primary interaction.** Every state change the dashboard can make
is reachable by speaking: discovery, retrieval, scoring explanations, applying,
moving an application between rounds, and scheduling interviews. Clicks are a
convenience layer over the same tool calls.

The one deliberate exception is **opening an external job posting**, which stays
a click. Browsers suppress `window.open` without user activation, and a tool call
arriving over a data channel has none. Voice marks a job applied; the click opens
the posting. See §7.

Voice runs through LiveKit in two personas — dashboard co-pilot and mock
interviewer — sharing one agent, one session, and one set of credentials, and
differing only in instructions and exposed tools.

**Demo thesis: the complete loop.** The submission argues that the whole
lifecycle works end to end — resume in, jobs scored, applied, tracked through
rounds, interview scheduled, mock interview done. Breadth over depth. Every
scoping decision in this document follows from that.

---

## 3. Product walkthrough

1. User drops a resume PDF onto the dashboard.
2. The app parses it and Gemini turns it into a structured profile: skills,
   seniority, titles, locations, years of experience.
3. **Matching jobs are fetched automatically** from that profile — no query typed
   or spoken. This is the primary discovery path.
4. Each job renders as a card with a match score, the specific skills that
   matched, the concrete gaps, and an **Open ↗** action.
5. Saying "apply to the Freshworks one" moves the job to **Applied** and arms its
   **Open ↗** button; the user clicks once to open the real posting.
6. The tracker advances the application through interview rounds, by click or by
   voice.
7. Saying "I have an interview with Freshworks on Tuesday at 3" creates a Google
   Calendar event through the already-authenticated Workspace MCP server.
8. Asking "what did I apply to at Freshworks?" or "show me everything in round
   two" retrieves stored jobs and applications and re-renders the work surface.
9. Selecting **Mock Interview** on any tracked job starts a live voice interview
   whose questions are generated from that job's description and the user's own
   gap list.

**Two discovery paths, both core.** The resume-derived fetch above runs
automatically on upload. Speaking a query — "show me backend jobs in Chennai" —
overrides the profile-derived query for that fetch and re-scores the new results
against the same stored profile. Neither is a fallback for the other; both ship.

**Retrieval is a third path over stored data.** The feed is a working surface
showing the last query; SQLite is the record. Anything acted on is durable and
reachable through §9's retrieval paths.

---

## 4. Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Next.js dashboard (browser)                                 │
│  app/layout.tsx ........... LiveKitRoom provider (never      │
│                             unmounts, above all route groups)│
│  app/(shell)/layout.tsx ... voice rail · loop spine · tracker │
│  app/(shell)/page.tsx ..... job feed                          │
│  app/(shell)/pipeline ..... stage views                       │
│  app/(shell)/search ....... retrieval results                 │
│  app/(focus)/practice ..... full-bleed mock interview         │
└──────────┬───────────────────────────────────┬───────────────┘
           │ WebRTC audio                      │ REST
           │ + data channel (UI events)        │ (upload, token, reads)
┌──────────▼──────────────────────────┐        │
│  LiveKit Agent worker (Python)      │        │
│  AgentSession                       │        │
│    llm = google.beta.realtime.      │        │
│          RealtimeModel(vertexai)    │        │
│    fallback = STT → LLM → TTS       │        │
│    mcp_servers = [WorkspaceMCP]     │        │
│  Personas: CoPilot | MockInterviewer│        │
│  @function_tool set                 │        │
└──────────┬──────────────────────────┘        │
           │                          ┌────────▼────────────────┐
           │                          │  FastAPI (uvicorn)      │
           │                          │  /upload  /token        │
           │                          │  /jobs  /applications   │
           │                          └────────┬────────────────┘
┌──────────▼───────────────────────────────────▼───────────────┐
│  Core services (Python) — imported in-process by both        │
│  jobs.py · scoring.py · profile.py · tracker.py · search.py  │
└──────────┬───────────────┬───────────────┬───────────────────┘
           ▼               ▼               ▼
     Adzuna API     Gemini 2.5 (Vertex)  SQLite (WAL)
     (+ seeded      scoring & profile    tracker.db
      fallback)
```

**Three processes:** `uvicorn` (FastAPI), the agent worker, and `next dev`. A
single start script runs all three so a dead worker cannot surface mid-recording.

**Why the agent imports core services rather than calling FastAPI.** Tool calls
sit inside the voice loop, where every millisecond is audible. In-process calls
avoid an HTTP hop. With one user and one SQLite file there is no consistency
problem worth paying that latency for. SQLite runs in WAL mode so both Python
processes can write.

**Why the LiveKit provider lives in the root layout.** Route groups with
different layouts unmount each other. If the room provider lived in the shell
layout, navigating to the full-bleed mock interview would tear down the voice
session. Hoisting the provider above both groups is what lets the takeover be a
real route. Only the visual chrome lives in `(shell)/layout.tsx`.

**Why the dashboard is not a separate app.** Every tool call publishes a
data-channel event to the room. The React app subscribes and re-renders. Job
cards animate in while the agent is still speaking. This is what makes it feel
like a command center rather than a chatbot with a sidebar.

---

## 5. Technology choices

| Layer | Choice | Reason |
|---|---|---|
| Voice transport | LiveKit Cloud (free tier) | Requested; no self-hosting |
| Voice + brain | Gemini Live via Vertex AI | Native speech-to-speech; lowest latency; runs on existing GCP creds; supports function calling |
| Voice fallback | LiveKit STT → LLM → TTS pipeline | Same transport, tools, and personas if Live is unavailable; higher latency is acceptable, silence is not |
| Batch reasoning | Gemini 2.5 (Flash for scoring, Pro for interview questions) via Vertex | Structured JSON output; latency irrelevant off the voice path |
| Calendar | Existing Google Workspace MCP server | Already OAuth-authenticated at `~/.google_workspace_mcp/credentials` |
| Job data | Adzuna (India endpoint) + seeded fallback dataset | Free tier, real Chennai coverage, `redirect_url` gives a genuine apply link |
| API server | FastAPI + uvicorn | Imports core services directly; minimal surface |
| Store | SQLite (WAL) | Single user, zero ops, two writer processes |
| Frontend | Next.js App Router + Tailwind + shadcn/ui + Lucide | Component library avoids hand-rolling UI under deadline |
| Motion | Framer Motion | `layoutId` gives shared-element transitions almost free |
| Agent runtime | Python 3.12 + `livekit-agents` | The mature LiveKit SDK; the Node SDK lags on Google plugins |

**Model IDs must be verified on Day 0.** Gemini Live preview model identifiers
change frequently; do not hardcode from memory. Confirm the current Live model
and region availability against Vertex before building on them.

**Python is not installed on the build machine.** Verified: the only `python.exe`
on `PATH` is the Windows Store alias stub. Node 22.14.0 is present. Installing
Python 3.12 is the first Day 0 task and blocks everything else.

---

## 6. Data model (SQLite)

```
profile(id, full_name, email, years_experience, seniority,
        skills_json, titles_json, locations_json, raw_text, created_at)

job(id, source, source_id, title, company, location, description,
    salary_min, salary_max, apply_url, posted_at, fetched_at)

match(id, job_id, profile_id, score, matched_skills_json,
      gaps_json, rationale, scored_at)

application(id, job_id, stage, applied_at, updated_at, notes)
  stage ∈ saved | applied | screening | round_1 | round_2 | final
          | offer | rejected

interview(id, application_id, round_label, scheduled_at,
          calendar_event_id, location, notes)

mock_session(id, job_id, started_at, ended_at, transcript, feedback_json)

fetch_run(id, query, source, ran_at, job_ids_json)
```

`fetch_run` records what the last query returned so the work surface can restore
itself on cold start rather than opening empty.

Retrieval queries `job`, `match`, and `application` directly; no separate history
table is needed.

---

## 7. Agent tools

Exposed to the **co-pilot** persona:

| Tool | Action |
|---|---|
| `fetch_jobs_for_profile()` | Build a query from the stored profile and fetch live listings |
| `search_jobs(query, location, remote)` | Ad-hoc voice-driven search that overrides the profile query |
| `score_jobs(job_ids)` | Batch 10 jobs into one Gemini call; write `match` rows |
| `explain_match(job_id)` | Speak the score, matched skills, and gaps for one job |
| `find_jobs(query)` | Retrieve stored jobs and applications by company, title, or stage |
| `save_job(job_id)` | Park a job at stage `saved` without applying |
| `mark_applied(job_id)` | Move to `applied` and arm the card's Open action |
| `advance_stage(job_id, stage)` | Move an application between rounds |
| `pipeline_status()` | Spoken summary of the whole tracker |
| `schedule_interview(job_id, when, round_label)` | Create a Calendar event via Workspace MCP; write an `interview` row |
| `start_mock_interview(job_id)` | Hand off to the mock interviewer persona |

Exposed to the **mock interviewer** persona: `end_mock_interview()` only. It has
read access to the JD and gap list through injected context, and deliberately no
ability to mutate the tracker.

**`mark_applied` never opens a URL.** It changes state and emits an event; the
card's **Open ↗** enters an armed, pulsing state that the user clicks. This keeps
the spoken path working and stays honest about what voice can drive.

**UI events.** Every tool publishes `{type, payload}` over the room data channel
so the dashboard stays in lockstep with what the agent just did:

`jobs.updated` · `scores.updated` · `application.moved` · `interview.scheduled` ·
`mode.changed` · `navigate`

`navigate` carries a path, letting the agent move the work surface without a
bespoke view-state protocol.

---

## 8. Scoring design

One Gemini 2.5 Flash call per batch of ten jobs, using structured output:

```json
{
  "results": [{
    "job_id": "string",
    "score": 0,
    "matched_skills": ["string"],
    "gaps": ["string"],
    "rationale": "one sentence"
  }]
}
```

Prompt constraints that matter:

- Score 0–100 against the **stored profile only**; never invent experience.
- Gaps must be concrete and checkable ("no Kubernetes experience listed"), never
  vague ("could be stronger").
- Rationale is capped at one sentence because it is rendered on a card and
  sometimes read aloud.

---

## 9. UI and UX

### Navigation model

**Persistent shell, routed center.** The voice rail, loop spine, and pipeline
tracker live in `(shell)/layout.tsx` and never unmount. Only the work surface is
a route.

| Route | Work surface shows |
|---|---|
| `/` | Job feed — results of the last fetch or spoken query |
| `/pipeline?stage=<stage>` | Applications filtered to one stage |
| `/search?q=<query>` | Retrieval results from `find_jobs` |
| `/practice/<jobId>` | Full-bleed mock interview (own route group, no shell chrome) |

Routing rather than React view state buys the browser back button, reload-safe
views, and deep links the agent can emit directly — all of which would otherwise
be hand-built. The rails never unmount, so agent-driven updates are always
visible regardless of route.

### Layout

- **Loop spine** (top, full width) — Discover → Score → Apply → Track → Schedule
  → Practice, each segment carrying a live count, the active segment lit while
  the agent works. This is what makes the complete loop legible to a viewer.

  Spine segments are loop *phases* and do not map one-to-one onto
  `application.stage` values. The mapping is explicit:

  | Segment | Count shown | Click navigates to |
  |---|---|---|
  | Discover | jobs in the current work surface | `/` |
  | Score | of those, how many have a `match` row | `/` |
  | Apply | applications at `applied` or beyond | `/pipeline?stage=applied` |
  | Track | applications in `screening`…`final` | `/pipeline?stage=interviewing` |
  | Schedule | future rows in `interview` | `/pipeline?stage=interviewing` |
  | Practice | rows in `mock_session` | most recent `/practice/<jobId>`, else inert |

  `?stage=` accepts any `application.stage` value plus the pseudo-value
  `interviewing`, which expands to `screening`…`final`.
- **Left rail** (~280px, fixed) — voice orb with speaking/listening state and the
  live transcript, rendered as an `aria-live` region. Voice only; nothing else.
- **Center** (flex) — the work surface. Job cards in a **single column**, not a
  grid, so they stay readable around 600px.
- **Right rail** (~320px, fixed) — pipeline tracker grouped by stage, `saved`
  first, groups collapsed by default with counts, plus an "Upcoming interviews"
  block sourced from the `interview` table.

### Work surface states

The center crossfades between three states in one container:

1. **Empty** — the resume dropzone, as one large obvious target. This is the
   demo's opening shot and the app's only onboarding.
2. **Loading** — skeleton cards. Fetch plus a scoring batch is several seconds
   and lands on the demo's most important beat; a spinner there reads as a hang.
3. **Loaded** — scored cards, or a retrieval result set with its query labelled
   and a path back to the feed.

**Cold start restores the last `fetch_run`** rather than opening empty. A restart
that looks like data loss is a bad thing to discover while recording.

### Cards

Score ring with tabular figures, company and title, matched skill chips, gap
chips in a warning tone carrying an icon rather than colour alone, and **Open ↗**.
Cards expand in place — not into a modal, so the spine stays visible — to reveal
the full JD, rationale, scheduled interviews, and past mock feedback. Expansion
is the only surface where `mock_session` feedback is readable.

### Motion

Applying a job animates the card from the work surface into its stage in the
right rail via Framer Motion `layoutId`. This shared-element transition is the
clearest visual proof that a spoken command caused a state change, and it costs
almost nothing to build.

### Visual system

Dark theme only — a command center reads dark, and one theme built well beats two
built badly under this deadline. Lucide icons throughout, no emoji. All motion
respects `prefers-reduced-motion`. Focus rings stay visible; the Open action,
stage controls, and expansion are keyboard reachable.

### Verify before Saturday

The three-panel layout plus spine is tight below 1280px wide. Confirm the build
machine's screen width and record at 1440×900 or wider.

---

## 10. Build schedule

Three buckets: Friday night, Saturday, Sunday. Scope is held at full; the cut
line is applied reactively at the tripwires below rather than up front.

**Friday night — setup, then one spike.**
Install Python 3.12 and the gcloud SDK. Create a venv and install
`livekit-agents` with the Google plugin. Create a service account with the Vertex
AI User role and download its JSON — the existing Workspace MCP credentials are
user OAuth and will not work for Vertex. Enable Gemini on Vertex and verify the
current Live model ID and region. Create a LiveKit Cloud project. Register for
Adzuna and confirm the India endpoint returns Chennai results. Then prove exactly
one thing: a bare LiveKit agent holding a voice conversation through Gemini Live.
Build nothing else tonight.

> **Tripwire A — 23:00 Friday.** If Gemini Live is not holding a conversation,
> stop debugging it and verify the STT → LLM → TTS pipeline path instead.
> Debugging a preview API past midnight is how Saturday disappears.

**Saturday — the spine.**
Morning: scaffold all three processes, SQLite schema, resume upload, parse, and
Gemini profile extraction; Adzuna fetch and the seeded fallback dataset.
Afternoon: batch scoring, job cards, the shell layout with rails and spine, and
the LiveKit token endpoint. Evening: co-pilot persona wired to
`fetch_jobs_for_profile`, `search_jobs`, and `explain_match`, with data-channel
events driving the UI.

> **Tripwire B — 13:00 Saturday.** Scored cards rendering, or the history layer
> is cut whole. It is the newest scope and goes first.
>
> **Tripwire C — 22:00 Saturday.** Voice driving the feed, or mock interview
> drops to scripted questions and calendar drops to a local row — decided
> Saturday night, not discovered Sunday afternoon.

End state: drop a resume, watch scored jobs appear, change the feed by speaking.

**Sunday — actions until noon, then ship.**
Morning: the Apply split, tracker stages, the history layer (`find_jobs`, saved
group, stage routes, card expansion), `schedule_interview` via Workspace MCP, and
the mock interviewer persona with its full-bleed route.

> **Tripwire D — 12:00 Sunday. Hard feature freeze.** Anything not working is cut
> per §12. No exceptions, however close it feels.

Afternoon: empty state and skeletons, dark pass, README, then two or three
rehearsals of the 4-minute demo and **record by 17:00**, leaving buffer before
the deadline. The video is a submission artifact, not a backup.

---

## 11. Risks

| Risk | Mitigation |
|---|---|
| Gemini Live model ID or region has moved since training data | Verify Friday night before any code depends on it |
| Gemini Live unavailable or unstable entirely | Tripwire A switches to the STT → LLM → TTS pipeline; same transport and tools |
| Vertex needs a service account, not the existing user OAuth | Explicit Friday-night setup step |
| Windows setup (Python, gcloud, service account) consumes the Friday spike | Setup is sequenced first and Tripwire A has a hard time on it |
| Gemini Live caps session length (historically ~10–15 min) | Keep mock interviews to 3–5 questions; do not design a 30-minute session |
| Workspace MCP server fails to attach to the agent | Fall back to direct Google Calendar REST with the same credentials |
| Adzuna rate limit or thin Chennai coverage kills the demo | Seed ~40 realistic Chennai listings locally as a fallback source |
| Voice-driven apply silently blocked by popup suppression | Apply is split: voice marks state, click opens the posting (§7) |
| Voice session torn down by navigation | LiveKit provider lives in the root layout, above all route groups (§4) |
| Three processes, one dead worker mid-recording | Single start script; verify all three during rehearsal |
| Scope exceeds the time available | Cut line below, applied at the tripwires |

---

## 12. Cut line

The demo thesis is the complete loop, so cuts remove **depth, never a stage**.
Every segment of the spine keeps working; it just works more simply. Apply in
this order:

1. Mock interview → three scripted questions from the JD, fixed feedback shape.
2. Calendar → local `interview` row, no real Calendar event.
3. Rounds → `applied` / `interviewing` / `closed`.
4. History → `find_jobs` only; drop spine filtering and card expansion.
5. Scoring → fewer jobs per fetch.

**Never cut:** all six spine stages working once each, the empty state, the
loading skeletons, and the recorded video.

---

## 13. Out of scope

**Deployment and hosting.** The app runs locally; the submission is the
repository plus a recorded demo video.

Also out of scope: auto-submitting applications to job boards (violates board
terms of service and breaks on captchas), multi-user accounts and auth, email
ingestion for automatic status detection, light theme, and mobile layout.
