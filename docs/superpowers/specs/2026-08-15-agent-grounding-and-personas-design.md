# Agent Grounding and Persona Lifecycle — Design Spec

- **Date:** 2026-08-15
- **Status:** Draft, awaiting review
- **Supersedes:** nothing; extends `2026-08-14-job-search-command-center-design.md`

---

## 1. Why this work exists

Live testing produced four apparently unrelated failures:

| Observed | Screenshot evidence |
|---|---|
| Assistant answered "When did World War 2 happen?" in full | Off-topic answer, no refusal |
| Assistant answered a World War I question with facts about the Taj Mahal | Wrong answer, confidently stated |
| "I cannot access your job applications or change their status" | Denied a capability the app ships |
| "Interview complete. Here is the feedback…" with no questions asked | Feedback for an interview that never happened |

All four share one cause.

### 1.1 Root cause: the persona handoff is a one-way door

`CoPilot.handle_ui_command` and `CoPilot.start_mock_interview` both hand off to
`MockInterviewer`. `MockInterviewer.end_mock_interview` saves the session,
publishes a `navigate` event pointing home, and returns the string
`"Interview complete."` — it never hands back.

`session.update_agent` appears exactly once in the codebase, and it only points
into the interviewer.

`MockInterviewer` declares one tool: `end_mock_interview`. It has no
`mark_applied`, no `advance_stage`, no `fetch_jobs_for_profile`, no
`pipeline_status`. So once a mock interview has run:

- The session is `MockInterviewer` for the rest of its life.
- "I cannot change their status" is **literally true** — the tools live on
  `CoPilot`, which is no longer running.
- Every later turn is answered by an agent instructed to conduct an interview,
  which explains both the off-topic answers and their confident tone.

The trigger is the fourth symptom: the model called `end_mock_interview`
immediately without asking anything, and because the door is one-way, the
session never recovered.

**One bug, four symptoms.** Fixing the lifecycle is the highest-value change in
this spec.

---

## 2. Scope

In scope:

1. Persona lifecycle — return to `CoPilot` when an interview ends
2. Grounding — the agent knows which jobs are on screen
3. Scope discipline — decline off-topic questions and redirect
4. Interview integrity — an interview cannot end before it happens
5. Question quality — interview questions informed by the résumé, not only the job
6. Merge the Discover and Score segments in the loop spine

Out of scope, recorded so it is not silently lost:

- Latency work (worker colocation, STT/LLM/TTS pipeline) — separate investigation
- Session-cleanup leaks and orphaned job processes — operational, not behavioural
- Expanding Workspace MCP beyond calendar — already connected, `--tools calendar`
  is a deliberate limit

---

## 3. Persona lifecycle

### 3.1 Decision

`end_mock_interview` returns the originating `CoPilot` instance. Handoff back
uses the same mechanism as handoff in: returning an `Agent` from a
`function_tool`.

`CoPilot._begin_mock_interview` passes `self` to the `MockInterviewer`
constructor, which stores it. The interview therefore returns to the *same*
co-pilot, preserving its chat context and its already-open DB connection.

### 3.2 Alternatives rejected

| Approach | Why not |
|---|---|
| `session.update_agent(CoPilot(room))` inside the tool | Builds a fresh co-pilot, discarding conversation history and reopening the DB |
| Single agent, swap instructions instead of personas | Removes this bug class, but the interviewer would retain every job tool and could mark a job applied mid-interview. Tool isolation is worth keeping |

### 3.3 The failure path matters most

The return must not depend on the save succeeding. If `save_session` or
`format_transcript` raises, the persona must **still** switch back, or a single
bad save strands the user in the interviewer — the exact state observed in
testing.

Implementation: wrap the persistence work so that a failure is logged and the
`CoPilot` is still returned. Ending an interview must never be able to leave the
session in the interviewer.

---

## 4. Grounding

### 4.1 Decision

`CoPilot.on_user_turn_completed(turn_ctx, new_message)` injects the current job
list into the chat context before each reply. The SDK documents this hook as the
place to update chat context before the LLM responds.

The data comes from the same source the UI reads, so the two cannot disagree.

### 4.2 Format

One line per job, cheap to read and unambiguous to reference:

```
#12 Graduate Engineer · Whirlpool · score 60 · applied
#13 AI Intern · Alphadot Technologies · score 55 · not tracked
```

Fields: job id, title, company, match score (or `unscored`), stage (or
`not tracked`).

### 4.3 Bounds

- Ordered by score descending, matching the work surface's own ordering.
- Capped at 20 entries.
- When the list is truncated, the injected block says so explicitly, so the
  agent does not claim a job does not exist when it is merely beyond the cap.
- When no jobs are loaded, the block says the feed is empty rather than being
  omitted, so the agent can say so instead of guessing.

### 4.4 Consequence

"Change the Whirlpool one to interviewing" resolves to `job_id 12` directly.
Without grounding, the agent must call `find_jobs` first, costing an extra
round trip — roughly 285 ms measured to us-central1 — and the model may skip the
lookup and invent an id.

---

## 5. Scope discipline

The current instructions describe what the agent does but never what it must
decline, which is why an unrelated history question received a confident answer.

Instructions gain:

- An explicit boundary: this assistant covers this user's job search — their
  jobs, applications, interviews, résumé, and pipeline.
- A redirect for anything outside it: one short sentence declining, naming what
  it can do instead. Not a lecture.
- An explicit carve-in for adjacent, useful questions: interview technique,
  how to answer a weakness question, what a role's responsibilities imply. These
  are in scope deliberately — a flat "job search only" refusal would reject them
  and make the assistant less useful.

---

## 6. Interview integrity

### 6.1 The problem

The instructions already said to ask three questions before giving feedback. The
model ignored them. An instruction is a request, not a constraint.

### 6.2 Decision

Enforce the rule in code. `end_mock_interview` inspects the chat context and
refuses to end if the candidate has not actually answered the questions,
returning a correction the model must act on rather than persisting an empty
session.

- The interviewer knows how many questions it was given (`len(questions)`).
- **The count must be relative, not absolute.** Personas share the session's
  chat context, so a `MockInterviewer` created mid-conversation inherits every
  user turn that preceded it. An absolute count would already exceed the bar on
  turn one and the guard would never fire. The interviewer therefore records the
  number of user turns present at construction as a baseline, and requires
  `len(questions)` *additional* user turns beyond it.
- If the bar is not met, the tool returns a message instructing the model to ask
  the next unanswered question, and **saves nothing**.

This makes "interview complete" impossible to reach without an interview, no
matter what the model decides.

### 6.3 Deliberate limitation

Counting user turns is a proxy for "the questions were asked and answered". A
candidate who says "yes" three times would pass the check. This is accepted: the
guard exists to stop the model skipping the interview outright, which is the
observed failure, not to grade answer quality.

---

## 7. Question quality

`build_questions` currently sees the job title, company, description, and the
recorded match gaps. It never sees the résumé itself.

It gains the stored profile from `get_profile`: skills, titles, years of
experience, seniority. The prompt then asks for questions probing the gap
between this candidate's actual background and this specific role.

Fallback behaviour is unchanged: when the model call fails, the existing
template questions are returned. The template already references the job and the
recorded gaps and remains correct.

When no profile is stored, the prompt omits the résumé section rather than
sending an empty one, and question generation still works from the job alone.

---

## 8. Loop spine: merge Discover and Score

`SEGMENTS` in `frontend/components/loop-spine.tsx` lists Discover and Score as
separate entries that both route to `/`. They collapse into one entry labelled
Discover.

The count shown is the number of jobs in the feed (`jobs.length`), matching the
segment's label and what is visibly on screen. Scoring runs automatically after
every fetch, so in practice the two counts were already equal — the screenshot
that prompted this change reads "Discover 20 / Score 20" — which is precisely
why showing both is redundant.

The comment in `loop-spine.tsx` about multiple segments mapping to one route,
and the `activeKey` logic it justifies, are re-evaluated: with Discover and
Score merged, the remaining duplicate pair is Track and Schedule, which both
point at `/pipeline?stage=interviewing`. The logic is still required and stays.

`counts.score` is no longer read by the spine. The key is removed from the
counts object built in `frontend/app/(shell)/layout.tsx` so no dead field is
computed.

---

## 9. Testing

Everything except section 8 is testable in pytest without a live model.

| Behaviour | Test |
|---|---|
| Ending an interview returns the co-pilot | The tool's return value is the originating `CoPilot` instance |
| A failed save still returns the co-pilot | Force `save_session` to raise; assert persona still switches back and the error is logged |
| Grounding lists current jobs | Injected text contains id, title, company, score, stage for seeded jobs |
| Grounding is capped and says so | With 30 jobs, at most 20 lines, and the truncation notice is present |
| Grounding handles an empty feed | States the feed is empty rather than emitting nothing |
| An interview cannot end early | With no candidate turns, `end_mock_interview` saves nothing and returns a correction |
| Inherited context does not satisfy the guard | Construct the interviewer on a context that already holds several user turns; ending immediately must still be refused |
| An interview can end normally | With enough candidate turns *beyond the baseline*, the session persists with transcript and feedback |
| Questions use the résumé | The prompt passed to the model contains stored skills |
| Questions work with no profile | No résumé section, generation still returns three questions |

Section 8 is verified by `npx tsc --noEmit`, `npx eslint`, and `npm run build`.

---

## 10. Files touched

**Backend**

| File | Change |
|---|---|
| `agent/personas.py` | Interviewer holds and returns the co-pilot; `end_mock_interview` guards early exit and survives save failure; `CoPilot.on_user_turn_completed` injects grounding; instructions gain scope boundary |
| `core/mock.py` | `build_questions` includes the stored profile |

**Frontend**

| File | Change |
|---|---|
| `components/loop-spine.tsx` | Discover and Score merged |
| `app/(shell)/layout.tsx` | `score` count removed from the counts object |

**Tests**

| File | Change |
|---|---|
| `tests/test_ui_commands.py` | Persona return, including the failed-save path |
| `tests/test_mock.py` | Early-exit guard, résumé in the prompt, no-profile case |
| `tests/test_personas_grounding.py` | New — grounding content, cap, empty feed |

---

## 11. Risks

| Risk | Mitigation |
|---|---|
| Grounding inflates every request's token count | Capped at 20 lines, one line each; measurable via the `LATENCY realtime tokens=` field already logged |
| The turn-count guard frustrates a legitimate short interview | The bar is the number of questions the interviewer was given, not an arbitrary constant |
| Returning the same `CoPilot` instance carries interview chat history into later turns | Accepted and intended — the co-pilot should know the interview happened |
