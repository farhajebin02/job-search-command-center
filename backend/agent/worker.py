import os

from dotenv import load_dotenv
from livekit.agents import AgentSession, JobContext, JobExecutorType, WorkerOptions, cli
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
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            job_executor_type=JobExecutorType.PROCESS,
        )
    )
