"""Per-turn latency instrumentation.

The realtime model is reached over a WebSocket to us-central1, which is the only
region serving Gemini Live models. That distance is a fixed cost on every turn,
so before changing anything about the audio stack it's worth knowing how much of
the delay is network, how much is the model thinking, and how much is turn
detection. These lines are what tell them apart.

Grep a run with:  Select-String worker.log -Pattern "LATENCY"
"""

from livekit.agents.metrics import (EOUMetrics, LLMMetrics, RealtimeModelMetrics,
                                    STTMetrics, TTSMetrics)

#: The SDK reports -1 when no audio token was ever produced for a turn.
_UNSET = -1


def _secs(value: float) -> str:
    """Render a duration, or "n/a" for the SDK's not-measured sentinel. Printing
    the raw -1 would read as a real (negative) measurement."""
    return "n/a" if value is None or value <= _UNSET else f"{value:.3f}s"


def format_metrics(ev) -> str | None:
    """One greppable line summarising a metrics event, or None if the event says
    nothing about latency."""
    if isinstance(ev, RealtimeModelMetrics):
        parts = [
            f"LATENCY realtime ttft={_secs(ev.ttft)}",
            f"response={_secs(ev.duration)}",
            f"tokens=in:{ev.input_tokens}/out:{ev.output_tokens}",
            f"conn={'reused' if ev.connection_reused else 'new'}",
        ]
        if ev.cancelled:
            parts.append("cancelled")
        return " ".join(parts)

    if isinstance(ev, EOUMetrics):
        # Only meaningful with local turn detection; the realtime model does its
        # own turn-taking server-side and will not emit this.
        return (f"LATENCY eou end_of_utterance={_secs(ev.end_of_utterance_delay)} "
                f"transcription={_secs(ev.transcription_delay)}")

    if isinstance(ev, LLMMetrics):
        return (f"LATENCY llm ttft={_secs(ev.ttft)} "
                f"total={_secs(ev.duration)} "
                f"tokens=in:{ev.prompt_tokens}/out:{ev.completion_tokens}")

    if isinstance(ev, TTSMetrics):
        return f"LATENCY tts ttfb={_secs(ev.ttfb)} total={_secs(ev.duration)}"

    if isinstance(ev, STTMetrics):
        return f"LATENCY stt total={_secs(ev.duration)} audio={_secs(ev.audio_duration)}"

    return None


class TurnLatency:
    """Felt latency: the gap between the user finishing a sentence and the agent
    starting to answer. This is the number a person actually experiences as lag.

    The SDK derives it as `e2e_latency`, but only on the pipeline path. The
    realtime path records `stopped_speaking_at` and `started_speaking_at` on the
    two messages and never subtracts them, so we do it here.
    """

    def __init__(self) -> None:
        self._user_stopped: float | None = None

    def observe(self, item) -> str | None:
        """Feed each conversation item as it is added. Returns a line when a
        reply can be measured against the user turn before it."""
        metrics = getattr(item, "metrics", None) or {}
        role = getattr(item, "role", None)

        if role == "user":
            self._user_stopped = metrics.get("stopped_speaking_at")
            return None

        if role != "assistant":
            return None

        started = metrics.get("started_speaking_at")
        if started is None or self._user_stopped is None:
            return None

        felt = started - self._user_stopped
        # Consume it: a follow-on agent turn is continuation, not a reply, and
        # measuring it against the same user turn would inflate the number.
        self._user_stopped = None
        return f"LATENCY turn felt={_secs(felt)}"
