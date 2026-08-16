"""The job process answers the supervisor's IPC health pings on its event loop
and is killed after `ping_timeout=60`. Tool work that blocks that loop (Adzuna
HTTP + Gemini scoring runs far longer than 60s) both starves audio handling and
gets the whole process killed mid-conversation, so blocking tools must hand off
to a worker thread."""
import asyncio
import time

from agent import tools


class _FakeParticipant:
    async def publish_data(self, *args, **kwargs):
        return None


class _FakeRoom:
    def __init__(self):
        self.local_participant = _FakeParticipant()

    def on(self, *args, **kwargs):
        return None


def _ticks_during_search(agent) -> int:
    """Count event-loop turns that complete while a 1s blocking tool runs."""
    async def run():
        ticks = 0

        async def heartbeat():
            nonlocal ticks
            while True:
                await asyncio.sleep(0.05)
                ticks += 1

        hb = asyncio.create_task(heartbeat())
        await asyncio.sleep(0)  # let the heartbeat reach its first await
        await agent.search_jobs(None, "backend", "Chennai")
        hb.cancel()
        return ticks

    return asyncio.run(run())


def test_blocking_tool_does_not_stall_the_event_loop(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(tools, "do_search",
                        lambda conn, query, location: time.sleep(1.0) or [])

    from agent.personas import CoPilot

    ticks = _ticks_during_search(CoPilot(_FakeRoom()))

    # ~20 turns are available in 1s at a 50ms beat; inline blocking yields 0.
    assert ticks >= 10, (
        f"event loop stalled during a 1s tool call: only {ticks} heartbeat "
        "turns completed, so IPC pings would go unanswered too"
    )
