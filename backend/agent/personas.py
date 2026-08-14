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
