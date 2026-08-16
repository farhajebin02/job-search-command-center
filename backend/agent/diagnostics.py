"""Evidence for the interruption bug.

The mock interview got stuck when the user talked over the agent, and there was
no way to tell which of two mechanisms was responsible: the SDK dropping a
handoff on interruption, or the completion guard refusing in a loop. Neither
leaves a trace by default.

Every line here is greppable and one line long, so a single reproduction run
answers the question:

    grep TURN     worker.log     what was said, and whether it was cut off
    grep TOOLS    worker.log     which tools ran, and whether their turn survived
    grep STATE    worker.log     agent state transitions (a stuck "thinking")
    grep INTERVIEW worker.log    answers counted against questions asked
"""

import logging

logger = logging.getLogger("jcc.turns")


def _clip(text: str, n: int = 60) -> str:
    text = (text or "").replace("\n", " ")
    return text if len(text) <= n else text[: n - 1] + "…"


def on_conversation_item(ev) -> None:
    """One line per message. `interrupted` is the whole point: it is the only
    place the SDK records that the user talked over the agent."""
    item = ev.item
    if getattr(item, "type", None) != "message":
        # Handoffs and config updates land here too; naming them is useful
        # because a handoff that never appears is itself the finding.
        logger.info("TURN type=%s", getattr(item, "type", type(item).__name__))
        return
    logger.info("TURN role=%s interrupted=%s text=%r",
                item.role, getattr(item, "interrupted", None),
                _clip(item.text_content or ""))


def on_function_tools_executed(ev) -> None:
    """Which tools ran and whether anything came back.

    On the realtime path an interrupted speech cancels the executor and
    returns without committing outputs, so a call logged here with no matching
    output is the dropped-work signature.
    """
    called = [c.name for c in ev.function_calls]
    returned = sum(1 for o in ev.function_call_outputs if o is not None)
    logger.info("TOOLS called=%s outputs=%d/%d",
                ",".join(called) or "-", returned, len(called))


def on_agent_state_changed(ev) -> None:
    """A session that stops responding usually stops in a state. Logging the
    transitions shows which one it stopped in."""
    logger.info("STATE %s -> %s", ev.old_state, ev.new_state)


def install(session) -> None:
    session.on("conversation_item_added", on_conversation_item)
    session.on("function_tools_executed", on_function_tools_executed)
    session.on("agent_state_changed", on_agent_state_changed)
