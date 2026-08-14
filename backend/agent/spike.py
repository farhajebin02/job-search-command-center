"""THROWAWAY spike — Task 0.7.

Proves exactly one thing: a LiveKit agent can hold a spoken conversation
through Gemini Live. No tools, no personas, no database. Deleted in Task 1.11
once the real co-pilot worker replaces it.

Run:  .venv\\Scripts\\python.exe -m agent.spike dev
Then connect at https://agents-playground.livekit.io
"""

import logging
import os

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobExecutorType,
    WorkerOptions,
    cli,
)
from livekit.plugins import google

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("spike")


async def entrypoint(ctx: JobContext):
    await ctx.connect()
    log.info("connected to room %s", ctx.room.name)

    session = AgentSession(
        llm=google.beta.realtime.RealtimeModel(
            model=os.environ["GEMINI_LIVE_MODEL"],
            vertexai=True,
            project=os.environ["GCP_PROJECT_ID"],
            location=os.environ["GCP_LOCATION"],
        )
    )

    await session.start(
        agent=Agent(
            instructions=(
                "You are a terse assistant being used to prove a voice pipeline "
                "works. Reply in one short sentence. If asked what you are, say "
                "you are the job search command center spike."
            )
        ),
        room=ctx.room,
    )
    await session.generate_reply(
        instructions="Greet the user in one short sentence and invite them to ask something."
    )


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            job_executor_type=JobExecutorType.PROCESS,
        )
    )
