import asyncio
import json
import logging
import os
import threading
from dataclasses import dataclass

from livekit.agents import Agent, function_tool, RunContext
from livekit.agents.llm import ChatContext

logger = logging.getLogger("jcc.agent")

from core.db import connect, init_db
from core.events import encode
from core import search as core_search, tracker
from agent import grounding, tools
# Aliased: `calendar` is also the name of this class's constructor argument,
# and of the stdlib module.
from agent import calendar as gcal

CO_PILOT_INSTRUCTIONS = (
    "You are the co-pilot for a job search command center. Be brief and "
    "concrete — one or two sentences per turn. When the user asks for jobs, "
    "call a tool rather than describing what you would do. Never invent a "
    "score, a company, or a job you have not fetched. After a tool runs, say "
    "what changed on screen in one sentence.\n\n"
    "SCOPE. You cover this user's job search: their jobs, applications, "
    "interviews, résumé, and pipeline. Interview technique and how to answer "
    "a specific question are in scope — they are part of preparing. General "
    "knowledge is not: trivia, history, science, news, coding help unrelated "
    "to their applications. Decline those in one short sentence and name "
    "something you can do instead. Do not lecture, and do not answer the "
    "question anyway.\n\n"
    "JOBS ON SCREEN. Each turn you are given the current feed with ids. Use "
    "those ids when calling tools. If the user names a company or role, match "
    "it against that list rather than guessing an id. If nothing matches, say "
    "so instead of picking the closest one.\n\n"
    "IDS. Never pass a job id you have not read, this turn, from the feed "
    "above or from a find_jobs result. Counts, positions in a list, and the "
    "order things were mentioned are not ids. If you do not have the id for "
    "the job the user means, call find_jobs first and use the id it returns. "
    "When a lookup is not an exact match, say which job you found and ask the "
    "user to confirm before you change anything."
)

#: How many hits find_jobs reads back. Enough to disambiguate out loud; past
#: this it is a list nobody can hold in their head.
MAX_RESULTS = 5

#: Tools that exist only while an interview is running. Everything else the
#: agent owns is a co-pilot tool. Gating on this is what keeps an interviewer
#: from answering "change my status" with a status change.
INTERVIEW_TOOL_NAMES = frozenset({"end_mock_interview", "abandon_interview"})


def interviewer_instructions(questions: list[str]) -> str:
    numbered = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))
    return (
        f"You are conducting a mock job interview. Ask these {len(questions)} "
        "questions one at a time, waiting for a full answer before moving on. "
        "Do not coach mid-interview. After the last answer, give brief "
        "feedback: two strengths and two specific improvements, then call "
        "end_mock_interview with that feedback.\n\n"
        "You are a professional interviewer and nothing else. You have no "
        "memory of any earlier conversation and no access to the candidate's "
        "job list or applications. Do not refer to anything outside this "
        "interview.\n\n"
        "The candidate is not trapped here. If they say they want to stop, "
        "change the subject, or ask for anything outside this interview — "
        "their job list, a status change, an unrelated question — call "
        "abandon_interview immediately. Never answer such a request with "
        "another interview question.\n\n"
        + numbered
    )


@dataclass
class Interview:
    """What is being practised right now. Its presence *is* the mode."""

    job_id: int
    questions: list[str]


class CoPilot(Agent):
    def __init__(self, room, calendar=None):
        super().__init__(instructions=CO_PILOT_INSTRUCTIONS)
        self._room = room
        #: The workspace-mcp server, so `schedule_interview` can write to Google
        #: Calendar itself. Registering it on the session alone only offers the
        #: calendar tools to the model, which then may or may not chain them
        #: onto a scheduling call. None when the server failed to start; the
        #: agent still runs, it just cannot write to the calendar.
        self._calendar = calendar
        self._local = threading.local()
        init_db(self._db())

        # Tools are partitioned once, here, because `Agent.__init__` collects
        # every decorated method on the class. Entering and leaving the
        # interview swaps between these two sets.
        found = self.tools
        self._interview_tools = [t for t in found
                                 if t.info.name in INTERVIEW_TOOL_NAMES]
        self._co_pilot_tools = [t for t in found
                                if t.info.name not in INTERVIEW_TOOL_NAMES]
        # No activity exists yet, which is exactly what `update_tools` does in
        # that case; it is async, and this is not.
        self._tools = list(self._co_pilot_tools)

        #: Set while an interview is running. Nothing else distinguishes the
        #: two modes — there is no second agent to hand off to, because the
        #: SDK discards handoffs whenever a speech is interrupted.
        self._interview: Interview | None = None
        #: The conversation to hand back after the interview. Isolation runs
        #: one way: the interview must not see this, but the user should not
        #: have to re-establish what they were doing before practising.
        self._saved_ctx: ChatContext | None = None

        logger.info("co-pilot ready with %d tools (%d reserved for interviews)",
                    len(self._tools), len(self._interview_tools))
        # The web UI publishes commands on the same data channel this agent
        # publishes events to, so buttons reach the same code paths as speech.
        # Logged because the same click was seen arriving twice, milliseconds
        # apart. If this line appears more than once per job, handlers are
        # accumulating on the room and that is the reason.
        logger.info("registering data handler on room %s", getattr(room, "name", "?"))
        room.on("data_received", lambda pkt: asyncio.create_task(
            self.handle_ui_command(pkt.data)))

    @property
    def interviewing(self) -> bool:
        return self._interview is not None

    def _db(self):
        """One SQLite connection per thread. Blocking tool work runs in a
        worker thread (see `_in_thread`) while fast tools stay on the event
        loop, so a single shared connection would be driven from two threads
        at once and hand back corrupted rows."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._local.conn = connect()
        return conn

    async def _in_thread(self, fn, *args):
        """Run blocking work (Adzuna HTTP, Gemini scoring) off the event loop.

        The job process answers the supervisor's IPC health pings on this loop
        and gets killed after `ping_timeout=60`. A fetch-and-score round trip
        runs well past that, so calling it inline both starves audio handling
        and gets the whole process killed mid-conversation. `_db()` is resolved
        inside the worker thread so it returns that thread's connection."""
        return await asyncio.to_thread(lambda: fn(self._db(), *args))

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        """Put the current feed in front of the model before it answers, so a
        reference like "the Whirlpool one" resolves to an id without a lookup
        round trip — or a guess."""
        if self._interview is not None:
            # Emptying the context on entry would be pointless if the job feed
            # were re-injected on the very next turn. An interviewer has no
            # business knowing what the candidate has applied to.
            #
            # Logged every turn so a stuck interview can be read back: if
            # `answered` stops climbing while turns keep arriving, the guard is
            # the thing refusing, not the model.
            logger.info("INTERVIEW job=%s answered=%d/%d",
                        self._interview.job_id, self._answers_given(),
                        len(self._interview.questions))
            return
        # The date goes in first, and separately. It needs no database, so a
        # feed lookup that fails must not take it down too -- without it the
        # scheduling tools get relative times resolved against the model's
        # training data.
        turn_ctx.add_message(role="system", content=grounding.today())
        try:
            jobs = await self._in_thread(grounding.current_jobs)
        except Exception:
            # Grounding is an enhancement; losing it must not kill the turn.
            logger.exception("could not build job grounding for this turn")
            return
        turn_ctx.add_message(role="system", content=jobs)

    def _job(self, job_id: int):
        """The job an id names, or None. Every tool that writes goes through
        this first: a hallucinated id is indistinguishable from a real one
        until it is looked up, and by then the wrong application has moved."""
        return self._db().execute(
            "SELECT id, title, company FROM job WHERE id=?", (job_id,)).fetchone()

    @staticmethod
    def _unknown_job(job_id: int) -> str:
        return (f"There is no job with id {job_id}, so nothing was changed. "
                "Do not guess ids. Call find_jobs, then use an id it returned.")

    @staticmethod
    def _name(row) -> str:
        """How a job is referred to back to the model, so that whatever it says
        next is anchored to the row that actually moved."""
        return f"#{row['id']} {row['title']} at {row['company']}"

    async def _publish(self, type: str, payload: dict) -> None:
        await self._room.local_participant.publish_data(
            encode(type, payload), reliable=True
        )

    @function_tool()
    async def fetch_jobs_for_profile(self, ctx: RunContext) -> str:
        """Fetch and score jobs matching the stored resume profile."""
        jobs = await self._in_thread(tools.do_fetch_for_profile)
        await self._publish("jobs.updated", {"count": len(jobs)})
        if not jobs:
            return "No profile is stored yet — ask the user to drop their resume."
        return f"Fetched and scored {len(jobs)} jobs."

    @function_tool()
    async def search_jobs(self, ctx: RunContext, query: str,
                          location: str = "Chennai") -> str:
        """Search live job listings for a role in a location, then score them."""
        jobs = await self._in_thread(tools.do_search, query, location)
        await self._publish("jobs.updated", {"count": len(jobs)})
        return f"Found {len(jobs)} jobs for {query} in {location}."

    @function_tool()
    async def explain_match(self, ctx: RunContext, job_id: int) -> str:
        """Explain the score, matched skills, and gaps for one job."""
        return tools.do_explain(self._db(), job_id)

    @function_tool()
    async def save_job(self, ctx: RunContext, job_id: int) -> str:
        """Save a job for later without applying to it. `job_id` must come from
        the feed or a find_jobs result — never from a count or a guess."""
        row = self._job(job_id)
        if row is None:
            return self._unknown_job(job_id)
        app = tracker.save_job(self._db(), job_id)
        await self._publish("application.moved",
                            {"job_id": job_id, "stage": app["stage"]})
        return f"Saved {self._name(row)} for later."

    @function_tool()
    async def mark_applied(self, ctx: RunContext, job_id: int) -> str:
        """Mark a job as applied. Does NOT open the posting — the user clicks
        Open. `job_id` must come from the feed or a find_jobs result — never
        from a count or a guess."""
        row = self._job(job_id)
        if row is None:
            return self._unknown_job(job_id)
        app = tracker.mark_applied(self._db(), job_id)
        await self._publish("application.moved",
                            {"job_id": job_id, "stage": app["stage"]})
        # Naming the row is the check on the sentence the model says next. It
        # once reported a Kotak Mahindra Bank role as applied having written to
        # an unrelated AI Intern posting, and nothing contradicted it.
        return (f"Marked {self._name(row)} as applied. Confirm that job by "
                "name to the user. The Open button on that card is ready "
                "whenever they want the posting.")

    @function_tool()
    async def advance_stage(self, ctx: RunContext, job_id: int, stage: str) -> str:
        """Move an application to a new stage, e.g. screening, round_1, offer.
        `job_id` must come from the feed or a find_jobs result — never from a
        count or a guess."""
        row = self._job(job_id)
        if row is None:
            return self._unknown_job(job_id)
        try:
            app = tracker.advance_stage(self._db(), job_id, stage)
        except ValueError as e:
            return str(e)
        await self._publish("application.moved",
                            {"job_id": job_id, "stage": app["stage"]})
        return (f"Moved {self._name(row)} to "
                f"{app['stage'].replace('_', ' ')}. Confirm that job by name "
                "to the user.")

    @function_tool()
    async def pipeline_status(self, ctx: RunContext) -> str:
        """Summarise every application in the pipeline."""
        return tracker.pipeline_summary(self._db())

    @function_tool()
    async def find_jobs(self, ctx: RunContext, query: str) -> str:
        """Retrieve previously seen jobs by company, title, or stage. Returns
        each job's id — pass those exact ids to the other tools."""
        found = core_search.find_jobs(self._db(), query)
        await self._publish("navigate", {"path": f"/search?q={query}"})
        if not found:
            return (f"Nothing matches {query!r}. Ask the user to say the "
                    "company or role again — do not act on a job you have "
                    "not found.")
        # Never lead with a bare count. The previous wording was "Found 1.
        # <title> at <company>." and the model read that 1 as the job id, then
        # applied to whichever job happened to be row 1 of the table.
        lines = "\n".join(
            f"{self._name(j)}"
            + (f" — {j['stage'].replace('_', ' ')}" if j.get("stage") else "")
            for j in found[:MAX_RESULTS])
        if not found[0].get("exact", True):
            return ("No exact match. The closest are below — these are guesses "
                    "at a misheard name, so name one to the user and get a yes "
                    f"before changing anything:\n{lines}")
        extra = (f"\n({len(found) - MAX_RESULTS} more not shown)"
                 if len(found) > MAX_RESULTS else "")
        return f"Matching jobs, with the ids to use:\n{lines}{extra}"

    @function_tool()
    async def schedule_interview(self, ctx: RunContext, job_id: int,
                                 when: str, round_label: str = "round_1") -> str:
        """Schedule an interview: records it on the dashboard and creates the
        event on the user's real Google Calendar. `when` must be an ISO 8601
        datetime — resolve "Tuesday at 3" to one before calling. `job_id` must
        come from the feed or a find_jobs result — never from a count or a
        guess."""
        from core.interviews import record_interview, set_calendar_event

        row = self._job(job_id)
        if row is None:
            return self._unknown_job(job_id)

        # The dashboard is written first, deliberately. It is the source of
        # truth for the pipeline, and going to Google first would leave a real
        # event on the user's calendar for an interview that then failed to
        # record (an untracked job raises below).
        try:
            iv = record_interview(self._db(), job_id, when, round_label, None)
        except ValueError as e:
            return str(e)
        await self._publish("interview.scheduled", {"job_id": job_id, "when": when})
        slot = f"{round_label.replace('_', ' ')} for {self._name(row)} at {when}"

        event = gcal.build_event(row, when, round_label)
        if self._calendar is None or event is None:
            return (f"Scheduled {slot} on the dashboard. It is NOT on their "
                    "Google Calendar — say so, and ask for an exact date and "
                    "time if you did not have one.")
        try:
            confirmation = await gcal.create_event(self._calendar, event)
        except Exception:
            # Never fatal: the interview is already recorded, and the user
            # needs to hear which half succeeded.
            logger.exception("Google Calendar write failed for job %s", job_id)
            return (f"Scheduled {slot} on the dashboard, but it could NOT be "
                    "added to their Google Calendar. Tell them it is not on "
                    "their calendar and they should add it themselves.")

        event_id = gcal.parse_event_id(confirmation)
        if event_id:
            set_calendar_event(self._db(), iv["id"], event_id)
        link = gcal.parse_event_link(confirmation)
        return (f"Scheduled {slot}, and it is on their Google Calendar."
                + (f" Link: {link}" if link else ""))

    @function_tool()
    async def set_reminder(self, ctx: RunContext, job_id: int, when: str,
                           about: str) -> str:
        """Put a follow-up reminder on the user's Google Calendar — chasing a
        recruiter, checking on an application, sending a thank-you note.
        `when` must be an ISO 8601 datetime; `about` is the short thing to do.
        For an actual interview use schedule_interview instead. `job_id` must
        come from the feed or a find_jobs result — never from a count or a
        guess."""
        row = self._job(job_id)
        if row is None:
            return self._unknown_job(job_id)

        # Nothing is written locally, so unlike schedule_interview there is no
        # dashboard row to fall back on: if Google refuses, the reminder simply
        # does not exist and the user has to be told exactly that.
        if self._calendar is None:
            return ("There is no calendar connected, so the reminder was NOT "
                    "created. Tell the user it did not happen.")
        event = gcal.build_reminder(row, when, about)
        if event is None:
            return (f"{when!r} is not a date and time, so the reminder was NOT "
                    "created. Ask the user for an exact day and time.")
        try:
            confirmation = await gcal.create_event(self._calendar, event)
        except Exception:
            logger.exception("Google Calendar reminder failed for job %s", job_id)
            return ("The reminder could NOT be added to their Google Calendar. "
                    "Tell the user it was not created and nothing was saved.")

        link = gcal.parse_event_link(confirmation)
        return (f"Reminder set for {when} to {about} — {self._name(row)}. "
                "It is on their Google Calendar."
                + (f" Link: {link}" if link else ""))

    async def enter_interview(self, job_id: int) -> None:
        """Become the interviewer.

        Every step here is a local mutation. That is the point: the previous
        design returned a second Agent from a tool, and the SDK drops a handoff
        whenever the speech carrying it is interrupted, which left the session
        stuck as an interviewer with no way back. Nothing below can be
        cancelled out from under us.
        """
        from core.mock import build_questions
        if self._interview is not None:
            # The model asked twice for one request. Re-entering would save the
            # already-emptied context as the thing to restore, throwing away
            # the conversation the user had before practising.
            logger.info("already interviewing for job %s, ignoring re-entry",
                        self._interview.job_id)
            return

        questions = await self._in_thread(build_questions, job_id)
        self._interview = Interview(job_id, questions)
        self._saved_ctx = self.chat_ctx.copy()

        # Order is load-bearing on Gemini Live, and getting it wrong killed the
        # session outright. `update_tools` marks the realtime session for
        # restart, and the replacement is seeded from whatever history the
        # plugin holds at that moment. `update_chat_ctx` cannot remove messages
        # there -- it appends a diff and then assumes the result -- so emptying
        # afterwards replayed the whole conversation into the new session while
        # leaving the plugin believing it was empty. The reconnect then sent a
        # batch Gemini rejected with 1007 "Content chunks have multiple roles",
        # unrecoverable. Empty first, so the restart is seeded clean.
        await self.update_chat_ctx(ChatContext.empty())
        await self.update_instructions(interviewer_instructions(questions))
        await self.update_tools(self._interview_tools)

        logger.info("interview mode on for job %s (%d questions)",
                    job_id, len(questions))
        await self._publish("navigate", {"path": f"/practice/{job_id}"})
        await self._publish("mode.changed", {"mode": "mock_interview"})

    async def leave_interview(self) -> None:
        """Become the co-pilot again, restoring the conversation the interview
        was isolated from."""
        job_id = self._interview.job_id if self._interview else None
        self._interview = None
        # Same ordering rule as entering: the context has to be what it should
        # be before the tool change restarts the realtime session.
        await self.update_chat_ctx(self._saved_ctx or ChatContext.empty())
        await self.update_instructions(CO_PILOT_INSTRUCTIONS)
        await self.update_tools(self._co_pilot_tools)
        self._saved_ctx = None

        logger.info("interview mode off for job %s", job_id)
        await self._publish("navigate", {"path": "/"})
        await self._publish("mode.changed", {"mode": "co_pilot"})

    @function_tool()
    async def start_mock_interview(self, ctx: RunContext, job_id: int) -> str:
        """Start a mock interview for one job, using an id from the feed or a
        find_jobs result."""
        row = self._job(job_id)
        if row is None:
            return self._unknown_job(job_id)
        await self.enter_interview(job_id)
        # Deliberately a string, not an Agent. Returning an Agent makes this a
        # handoff, and handoffs do not survive an interruption.
        return (f"Interview started for {self._name(row)}. Ask the first "
                "question now.")

    async def handle_ui_command(self, data: bytes) -> None:
        """Run a command published by the web UI on the data channel. Anything
        unrecognised — including this agent's own outbound events, which echo
        back on the same channel — is ignored."""
        try:
            evt = json.loads(data.decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if not isinstance(evt, dict) or evt.get("type") != "ui.command":
            # Our own outbound events echo back here; only log at debug so the
            # console isn't flooded, but keep it visible when hunting.
            logger.debug("data packet ignored, type=%r",
                         evt.get("type") if isinstance(evt, dict) else type(evt).__name__)
            return
        payload = evt.get("payload") or {}
        command = payload.get("command")
        if command not in ("start_mock_interview", "end_practice"):
            logger.warning("ignoring unknown ui.command %r", command)
            return

        # No session lookup any more. There is one agent, so a mode switch is
        # a local call — which also means these commands work before the
        # session has started and after any number of interruptions.
        if command == "end_practice":
            logger.info("ui.command end_practice — leaving interview mode")
            await self.leave_interview()
            return

        job_id = int(payload["job_id"])
        logger.info("ui.command start_mock_interview job_id=%s", job_id)
        try:
            await self.enter_interview(job_id)
        except Exception:
            # The caller is a bare create_task, so anything raised here would
            # vanish into a task nobody awaits and the click would look like it
            # did nothing at all.
            logger.exception("failed to start mock interview for job %s", job_id)

    # ---- interview mode -------------------------------------------------
    # Present on the same agent, hidden from the tool list unless an interview
    # is running (see INTERVIEW_TOOL_NAMES).

    def _answers_given(self) -> int:
        """Answers given in this interview. The context is emptied on entry,
        so every user turn in it is an answer — no baseline arithmetic, which
        is what the previous counter got wrong."""
        return sum(1 for m in self.chat_ctx.messages() if m.role == "user")

    @function_tool()
    async def abandon_interview(self, ctx: RunContext) -> str:
        """Leave the mock interview without finishing it. Call this the moment
        the candidate wants to stop, changes the subject, or asks for anything
        that is not part of this interview — a status change, their job list,
        or any other request. Saves nothing."""
        logger.info("interview abandoned for job %s",
                    self._interview.job_id if self._interview else None)
        await self.leave_interview()
        return "Interview cancelled. You are the co-pilot again."

    @function_tool()
    async def end_mock_interview(self, ctx: RunContext, strengths: list[str],
                                 improvements: list[str]) -> str:
        """End the mock interview. Pass the two strengths and two improvements
        you just gave as spoken feedback, so they're saved to the dashboard."""
        from core.mock import format_transcript, save_session

        if self._interview is None:
            return "There is no interview running."

        # Instructions alone did not hold: in testing the model jumped straight
        # to feedback for an interview it never conducted. Refuse in code.
        answered = self._answers_given()
        questions = self._interview.questions
        if answered < len(questions):
            nxt = questions[answered]
            logger.info("refusing to end interview: %d of %d answered",
                        answered, len(questions))
            return (f"The interview is not finished — {answered} of "
                    f"{len(questions)} questions answered. Ask this one "
                    f"next and wait for the answer: {nxt}\n"
                    "If the candidate does not want to continue the interview, "
                    "or is asking about something else entirely, call "
                    "abandon_interview instead of asking again.")

        job_id = self._interview.job_id
        try:
            await self._in_thread(save_session, job_id,
                                  format_transcript(self.chat_ctx),
                                  {"strengths": strengths,
                                   "improvements": improvements})
        except Exception:
            # Whatever happens to the record, the mode must still switch back.
            logger.exception("failed to save mock interview for job %s", job_id)

        await self.leave_interview()
        return "Interview complete and saved."
