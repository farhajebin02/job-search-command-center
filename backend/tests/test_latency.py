from livekit.agents.metrics import (EOUMetrics, LLMMetrics,
                                    RealtimeModelMetrics, TTSMetrics)

from agent import latency


def _realtime(**over):
    base = dict(
        request_id="r1", timestamp=0.0, duration=1.2, ttft=0.84,
        input_tokens=1500, output_tokens=80, total_tokens=1580,
        input_token_details=RealtimeModelMetrics.InputTokenDetails(),
        output_token_details=RealtimeModelMetrics.OutputTokenDetails(),
    )
    return RealtimeModelMetrics(**{**base, **over})


def test_realtime_line_leads_with_time_to_first_audio():
    # ttft is the number that answers "why does it feel slow" — it must be the
    # first thing on the line.
    line = latency.format_metrics(_realtime())
    assert line is not None
    assert line.startswith("LATENCY realtime ttft=0.840s")


def test_realtime_line_reports_response_duration_and_tokens():
    line = latency.format_metrics(_realtime())
    assert "response=1.200s" in line
    assert "tokens=in:1500/out:80" in line


def test_missing_ttft_is_reported_as_unavailable_not_as_a_negative_time():
    # The SDK uses -1 to mean "no audio token was ever sent". Printing that as
    # a duration would look like a real measurement.
    line = latency.format_metrics(_realtime(ttft=-1))
    assert "ttft=n/a" in line
    assert "-1" not in line


def test_cancelled_realtime_turn_is_flagged():
    line = latency.format_metrics(_realtime(cancelled=True))
    assert "cancelled" in line


def test_eou_line_reports_turn_detection_delay():
    line = latency.format_metrics(EOUMetrics(
        timestamp=0.0, end_of_utterance_delay=0.51,
        transcription_delay=0.09, on_user_turn_completed_delay=0.01))
    assert line is not None
    assert "LATENCY eou" in line
    assert "end_of_utterance=0.510s" in line
    assert "transcription=0.090s" in line


def test_llm_line_reports_ttft_for_a_pipeline_setup():
    line = latency.format_metrics(LLMMetrics(
        label="llm", request_id="r", timestamp=0.0, duration=0.9, ttft=0.31,
        cancelled=False, completion_tokens=20, prompt_tokens=100,
        prompt_cached_tokens=0, total_tokens=120, tokens_per_second=22.0))
    assert line is not None
    assert "LATENCY llm" in line
    assert "ttft=0.310s" in line


def test_tts_line_reports_time_to_first_byte():
    line = latency.format_metrics(TTSMetrics(
        label="tts", request_id="r", timestamp=0.0, ttfb=0.14, duration=0.8,
        audio_duration=2.0, cancelled=False, characters_count=40, streamed=True))
    assert line is not None
    assert "LATENCY tts" in line
    assert "ttfb=0.140s" in line


def test_unrecognised_metric_produces_no_line():
    # Silence beats a junk line for metric types that say nothing about latency.
    assert latency.format_metrics(object()) is None


def _msg(role, **metrics):
    from livekit.agents import llm
    m = llm.ChatMessage(role=role, content=["x"])
    m.metrics = metrics
    return m


def test_felt_latency_is_the_gap_between_user_stopping_and_agent_starting():
    # The SDK computes this as e2e_latency, but only on the pipeline path; the
    # realtime path records both timestamps and never the difference.
    tracker = latency.TurnLatency()
    assert tracker.observe(_msg("user", stopped_speaking_at=100.0)) is None
    line = tracker.observe(_msg("assistant", started_speaking_at=100.75))
    assert line == "LATENCY turn felt=0.750s"


def test_felt_latency_needs_a_user_turn_first():
    # A greeting the agent volunteers has no preceding user turn to measure from.
    tracker = latency.TurnLatency()
    assert tracker.observe(_msg("assistant", started_speaking_at=5.0)) is None


def test_each_user_turn_is_measured_only_once():
    tracker = latency.TurnLatency()
    tracker.observe(_msg("user", stopped_speaking_at=10.0))
    assert tracker.observe(_msg("assistant", started_speaking_at=10.5)) is not None
    # A second agent turn without new user speech is continuation, not a reply.
    assert tracker.observe(_msg("assistant", started_speaking_at=12.0)) is None


def test_turns_missing_timestamps_are_skipped():
    tracker = latency.TurnLatency()
    tracker.observe(_msg("user"))
    assert tracker.observe(_msg("assistant", started_speaking_at=3.0)) is None
