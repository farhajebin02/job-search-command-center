import os

from livekit.agents import Agent, function_tool, RunContext

from core.db import connect, init_db
from core.events import encode
from core import search as core_search, tracker
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

    @function_tool()
    async def schedule_interview(self, ctx: RunContext, job_id: int,
                                 when: str, round_label: str = "round_1") -> str:
        """Schedule an interview. `when` must be an ISO 8601 datetime."""
        from core.interviews import record_interview
        iv = record_interview(self._conn, job_id, when, round_label, None)
        await self._publish("interview.scheduled", {"job_id": job_id, "when": when})
        return (f"Scheduled {round_label.replace('_', ' ')} for job {job_id} "
                f"at {when}. Interview id {iv['id']}.")
