# Job Search Command Center — Design Spec

- **Date:** 2026-08-14
- **Deadline:** Sunday 2026-08-16 (~3 working days)
- **Context:** Company assessment submission
- **Status:** Draft, awaiting review

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
| Agent reasons and takes actions | Tool-calling agent that fetches, scores, applies, tracks, and schedules |
| UI/UX is our call | Single-screen three-panel command center |
| Heavy AI use while building | Built with Claude Code throughout |

**Voice is the primary interaction.** Everything the dashboard does is reachable
by speaking to it: discovery, scoring explanations, applying, moving an
application between rounds, and scheduling interviews. Clicks are a convenience
layer over the same tool calls, never the only way to do something.

Voice runs through LiveKit in two personas — dashboard co-pilot and mock
interviewer — sharing one agent, one session, and one set of credentials, and
differing only in instructions and exposed tools.

---

## 3. Product walkthrough

1. User drops a resume PDF onto the dashboard.
2. The app parses it and Gemini turns it into a structured profile: skills,
   seniority, titles, locations, years of experience.
3. **Matching jobs are fetched automatically** from that profile — no query typed
   or spoken. This is the primary discovery path.
4. Each job renders as a card with a match score, the specific skills that
   matched, the concrete gaps, and an **Apply ↗** button.
5. Clicking Apply opens the real employer/portal URL in a new tab and moves the
   job to **Applied** in the tracker.
6. The tracker advances the application through interview rounds, by click or by
   voice.
7. Saying "I have an interview with Freshworks on Tuesday at 3" creates a Google
   Calendar event through the already-authenticated Workspace MCP server.
8. Selecting **Mock Interview** on any tracked job starts a live voice interview
   whose questions are generated from that job's description and the user's own
   gap list.

**Two discovery paths, both core.** The resume-derived fetch above runs
automatically on upload. Speaking a query — "show me backend jobs in Chennai" —
overrides the profile-derived query for that fetch and re-scores the new results
against the same stored profile. Neither is a fallback for the other; both ship.

---

## 4. Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Next.js dashboard (browser)                            │
│  @livekit/components-react · shadcn/ui · Tailwind       │
│  voice orb · transcript · job feed · pipeline tracker   │
└──────────┬──────────────────────────────┬───────────────┘
           │ WebRTC audio                 │ REST
           │ + data channel (UI events)   │ (upload, tracker reads)
┌──────────▼──────────────────────────┐   │
│  LiveKit Agent worker (Python)      │   │
│  AgentSession                       │   │
│    llm = google.beta.realtime.      │   │
│          RealtimeModel(vertexai)    │   │
│    mcp_servers = [WorkspaceMCP]     │   │
│  Personas: CoPilot | MockInterviewer│   │
│  @function_tool set                 │   │
└──────────┬──────────────────────────┘   │
           │                              │
┌──────────▼──────────────────────────────▼───────────────┐
│  Core services (Python, shared by agent and API)        │
│  jobs.py · scoring.py · profile.py · tracker.py         │
└──────────┬───────────────┬───────────────┬──────────────┘
           ▼               ▼               ▼
     Adzuna API     Gemini 2.5 (Vertex)  SQLite
     (+ fallback)   scoring & profile    tracker.db
```

**Why one agent, two personas.** LiveKit supports handing off between `Agent`
instances inside a live session. The co-pilot and the mock interviewer share
transport, credentials, and the session; they differ in instructions and in which
tools are exposed. The mock interviewer deliberately gets *no* mutation tools.

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
| Batch reasoning | Gemini 2.5 (Flash for scoring, Pro for interview questions) via Vertex | Structured JSON output; latency irrelevant off the voice path |
| Calendar | Existing Google Workspace MCP server | Already OAuth-authenticated at `~/.google_workspace_mcp/credentials` |
| Job data | Adzuna (India endpoint) + seeded fallback dataset | Free tier, real Chennai coverage, `redirect_url` gives a genuine apply link |
| Store | SQLite | Single user, zero ops |
| Frontend | Next.js + Tailwind + shadcn/ui | Component library avoids hand-rolling UI under deadline |
| Agent runtime | Python 3.12 + `livekit-agents` | The mature LiveKit SDK; the Node SDK lags on Google plugins |

**Model IDs must be verified on Day 0.** Gemini Live preview model identifiers
change frequently; do not hardcode from memory. Confirm the current Live model
and region availability against Vertex before building on them.

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
```

---

## 7. Agent tools

Exposed to the **co-pilot** persona:

| Tool | Action |
|---|---|
| `fetch_jobs_for_profile()` | Build a query from the stored profile and fetch live listings |
| `search_jobs(query, location, remote)` | Ad-hoc voice-driven search that overrides the profile query |
| `score_jobs(job_ids)` | Batch 10 jobs into one Gemini call; write `match` rows |
| `explain_match(job_id)` | Speak the score, matched skills, and gaps for one job |
| `mark_applied(job_id)` | Move to `applied`; also fired by the Apply button |
| `advance_stage(job_id, stage)` | Move an application between rounds |
| `pipeline_status()` | Spoken summary of the whole tracker |
| `schedule_interview(job_id, when, round_label)` | Create a Calendar event via Workspace MCP; write an `interview` row |
| `start_mock_interview(job_id)` | Hand off to the mock interviewer persona |

Exposed to the **mock interviewer** persona: `end_mock_interview()` only. It has
read access to the JD and gap list through injected context, and deliberately no
ability to mutate the tracker.

**UI events.** Every tool publishes `{type, payload}` over the room data channel
(`jobs.updated`, `scores.updated`, `application.moved`, `interview.scheduled`,
`mode.changed`) so the dashboard stays in lockstep with what the agent just did.

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

## 9. UI layout

Single screen, three panels, no routing.

- **Left rail** — voice orb with speaking/listening state, live transcript,
  Co-pilot ⇄ Mock Interview toggle, resume upload dropzone.
- **Center** — job feed. Cards show score ring, company and title, matched skill
  chips, gap chips in a warning tone, and **Apply ↗**.
- **Right** — pipeline tracker grouped by stage, plus an "Upcoming interviews"
  block sourced from the `interview` table.

Apply is optimistic: open the URL, move the card, let the agent confirm verbally,
reconcile if the write fails.

---

## 10. Build schedule

**Day 0 — tonight, 2–3h, setup and one spike.**
Install Python 3.12 and gcloud. Create a service account with the Vertex AI User
role and download its JSON — the existing Workspace MCP credentials are user
OAuth and will not work for Vertex. Enable Gemini on Vertex, verify the current
Live model ID, create a LiveKit Cloud project, register for Adzuna and confirm
the India endpoint returns Chennai results. Then prove exactly one thing: a bare
LiveKit agent holding a voice conversation through Gemini Live. Build nothing
else until that works.

**Day 1 — the spine.**
Resume upload, parse, and profile extraction. Auto-fetch on upload. Batch
scoring. Job cards rendering live with scores, gaps, and apply links. Co-pilot
voice persona wired with `fetch_jobs_for_profile`, `search_jobs`, and
`explain_match`. End state: drop a resume, watch scored jobs appear, ask for
Chennai jobs by voice and watch the feed change.

**Day 2 — actions.**
Apply-click status flip. Tracker with round stages, click and voice driven.
Workspace MCP wired for `schedule_interview`. Mock interviewer persona with
JD-derived questions and end-of-session feedback.

**Day 3 morning — ship.**
Dashboard polish, rehearsed 4-minute demo, README, and the recorded demo video —
which is a submission artifact, not a backup. Leave the rest as buffer.

---

## 11. Risks

| Risk | Mitigation |
|---|---|
| Gemini Live model ID or region has moved since training data | Verify on Day 0 before any code depends on it |
| Vertex needs a service account, not the existing user OAuth | Explicit Day 0 setup step |
| Gemini Live caps session length (historically ~10–15 min) | Keep mock interviews to 3–5 questions; do not design a 30-minute session |
| Workspace MCP server fails to attach to the agent | Fall back to direct Google Calendar REST with the same credentials |
| Adzuna rate limit or thin Chennai coverage kills the demo | Seed ~40 realistic Chennai listings locally as a fallback source |
| Scope exceeds the time available | Cut line below, applied in order |

---

## 12. Cut line

Drop in this order if behind, never touching the spine:

1. Mock interview shrinks to a single scripted round with canned feedback.
2. Calendar integration becomes a local reminder row rather than a real event.
3. Round tracking collapses to applied/interviewing/closed.

**The spine — never cut:** voice co-pilot → resume upload → auto-fetch →
voice-driven location search → scored cards with gaps → working apply link.

---

## 13. Out of scope

**Deployment and hosting.** The app runs locally; the submission is the
repository plus a recorded demo video.

Also out of scope: auto-submitting applications to job boards (violates board
terms of service and breaks on captchas), multi-user accounts and auth, email
ingestion for automatic status detection, and mobile layout.
