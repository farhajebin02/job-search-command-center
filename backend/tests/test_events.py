import json
from core.events import encode, EVENT_TYPES


def test_encode_produces_utf8_json_with_type_and_payload():
    raw = encode("jobs.updated", {"count": 3})
    assert json.loads(raw.decode()) == {"type": "jobs.updated", "payload": {"count": 3}}


def test_encode_rejects_unknown_event_type():
    try:
        encode("not.a.real.event", {})
    except ValueError as e:
        assert "not.a.real.event" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_every_spec_event_type_is_registered():
    # Keep in step with the JccEvent union in frontend/lib/events.ts — the two
    # halves of this contract have to agree for the data channel to work.
    assert EVENT_TYPES == {
        # Outbound: agent -> UI.
        "jobs.updated", "scores.updated", "application.moved",
        "interview.scheduled", "mode.changed", "navigate",
        # Inbound: UI -> agent.
        "ui.command",
    }
