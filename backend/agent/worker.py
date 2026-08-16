import logging
import multiprocessing
import os
import sys

from dotenv import load_dotenv
from livekit.agents import AgentSession, JobContext, JobExecutorType, RoomInputOptions, WorkerOptions, cli
from livekit.agents import mcp
from livekit.plugins import google

from agent import diagnostics, latency
from agent.personas import CoPilot

load_dotenv()

logger = logging.getLogger("jcc.latency")

# workspace-mcp's --single-user mode picks the "first" credentials file
# (alphabetically sorted) from ~/.google_workspace_mcp/credentials/ when no
# email is specified. That directory holds credentials for more than one
# Google account on this machine, so leaving the email unset would silently
# pick the wrong one. Setting USER_GOOGLE_EMAIL forces the server to load
# credentials for this specific account instead of guessing.
def _resolve_workspace_mcp_user_email() -> str:
    return os.environ.get("WORKSPACE_MCP_USER_EMAIL", "farhajebin02@gmail.com")


def build_calendar_server() -> mcp.MCPServerStdio:
    """The workspace-mcp connection, built once and shared.

    One server, two consumers: the session registers its tools so the model can
    read the calendar, and `CoPilot` holds the same object so scheduling can
    write to it directly. Building it twice would spawn a second uvx process.
    """
    return mcp.MCPServerStdio(
        command="uvx",
        args=["workspace-mcp", "--single-user", "--tools", "calendar"],
        env={**os.environ,
             "USER_GOOGLE_EMAIL": _resolve_workspace_mcp_user_email()},
        # `uvx workspace-mcp` needs ~21s to come up on this machine; the
        # default 5s initialize timeout expires first, so setup fails and
        # the calendar tools silently never register.
        client_session_timeout_seconds=60,
    )


async def entrypoint(ctx: JobContext):
    await ctx.connect()
    calendar_server = build_calendar_server()
    session = AgentSession(
        llm=google.beta.realtime.RealtimeModel(
            model=os.environ["GEMINI_LIVE_MODEL"],
            vertexai=True,
            project=os.environ["GCP_PROJECT_ID"],
            location=os.environ["GCP_LOCATION"],
        ),
        mcp_servers=[calendar_server],
    )
    # Per-turn latency instrumentation. Two sources, because neither covers the
    # whole picture on a realtime model:
    #
    #   metrics_collected      deprecated, but the only place RealtimeModelMetrics
    #                          (and therefore ttft) surfaces. Its replacement,
    #                          ChatMessage.metrics, records no ttft on the
    #                          realtime path -- only the speaking timestamps.
    #   conversation_item_added the non-deprecated path, carrying those
    #                          timestamps, from which felt latency is derived.
    turn = latency.TurnLatency()

    @session.on("metrics_collected")
    def _on_metrics(ev) -> None:
        line = latency.format_metrics(ev.metrics)
        if line:
            logger.info(line)

    @session.on("conversation_item_added")
    def _on_item(ev) -> None:
        line = turn.observe(ev.item)
        if line:
            logger.info(line)

    # Per-turn evidence: which turns were interrupted, which tools ran, and
    # what state the agent stopped in. Off by default in the SDK, and the one
    # thing missing every time the interview got stuck.
    diagnostics.install(session)

    # The frontend always joins the same fixed room, and LiveKit dispatches one
    # job per room. Closing the session when the browser disconnects (the
    # default) leaves the agent participant in the room with a dead session, so
    # a page reload rejoins a room that already has an "agent" and never gets a
    # new job dispatched -- the mic works but nothing ever answers. Staying open
    # lets RoomIO re-link to the participant when it reconnects.
    #
    # One agent for both modes. Practice used to hand off to a second Agent
    # returned from a tool, but the SDK discards a handoff whenever the speech
    # carrying it is interrupted, which stranded the session in the interviewer.
    # `CoPilot` now switches modes in place, so nothing can be cancelled.
    pilot = CoPilot(ctx.room, calendar=calendar_server)

    await session.start(
        agent=pilot,
        room=ctx.room,
        room_input_options=RoomInputOptions(close_on_disconnect=False),
    )
    await session.generate_reply(
        instructions="Greet the user in one sentence and offer to find jobs."
    )


if __name__ == "__main__":
    # On this machine's venv, multiprocessing's Windows "spawn" respawn
    # resolves to the venv's *base* interpreter (pyvenv.cfg's `home`)
    # instead of the venv's own python.exe, so job/inference subprocesses
    # come up without any of the venv's installed packages (e.g. livekit
    # itself) and crash before publishing agent state -- which is why the
    # frontend's mic indicator gets stuck on "Idle". Forcing the executable
    # here overrides that resolution for every spawn this process performs.
    multiprocessing.set_executable(sys.executable)
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            job_executor_type=JobExecutorType.PROCESS,
        )
    )
