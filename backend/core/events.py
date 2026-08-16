import json

EVENT_TYPES = {
    "jobs.updated", "scores.updated", "application.moved",
    "interview.scheduled", "mode.changed", "navigate",
    # Inbound: published by the web UI, consumed by the agent.
    "ui.command",
}


def encode(type: str, payload: dict) -> bytes:
    if type not in EVENT_TYPES:
        raise ValueError(f"Unknown event type: {type}")
    return json.dumps({"type": type, "payload": payload}).encode("utf-8")
