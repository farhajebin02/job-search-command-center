import os

from dotenv import load_dotenv
from livekit.agents import AgentSession, JobContext, JobExecutorType, WorkerOptions, cli
from livekit.agents import mcp
from livekit.plugins import google

from agent.personas import CoPilot

load_dotenv()

# workspace-mcp's --single-user mode picks the "first" credentials file
# (alphabetically sorted) from ~/.google_workspace_mcp/credentials/ when no
# email is specified. That directory holds credentials for more than one
# Google account on this machine, so leaving the email unset would silently
# pick the wrong one. Setting USER_GOOGLE_EMAIL forces the server to load
# credentials for this specific account instead of guessing.
def _resolve_workspace_mcp_user_email() -> str:
    return os.environ.get("WORKSPACE_MCP_USER_EMAIL", "farhajebin02@gmail.com")


WORKSPACE_MCP_USER_EMAIL = _resolve_workspace_mcp_user_email()


async def entrypoint(ctx: JobContext):
    await ctx.connect()
    session = AgentSession(
        llm=google.beta.realtime.RealtimeModel(
            model=os.environ["GEMINI_LIVE_MODEL"],
            vertexai=True,
            project=os.environ["GCP_PROJECT_ID"],
            location=os.environ["GCP_LOCATION"],
        ),
        mcp_servers=[mcp.MCPServerStdio(
            command="uvx",
            args=["workspace-mcp", "--single-user", "--tools", "calendar"],
            env={**os.environ, "USER_GOOGLE_EMAIL": WORKSPACE_MCP_USER_EMAIL},
        )],
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
