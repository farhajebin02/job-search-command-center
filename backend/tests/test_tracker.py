import pytest
from core.db import connect, init_db
from core import tracker


def _conn(tmp_path):
    c = connect(str(tmp_path / "t.db"))
    init_db(c)
    for i in range(3):
        c.execute("INSERT INTO job (source, source_id, title, company, location, "
                  "apply_url) VALUES ('seed',?,?,'Co','Chennai','u')",
                  (f"s{i}", f"Job {i}"))
    c.commit()
    return c


def test_mark_applied_creates_application_at_applied(tmp_path):
    conn = _conn(tmp_path)
    app = tracker.mark_applied(conn, 1)
    assert app["stage"] == "applied"
    assert app["applied_at"] is not None


def test_mark_applied_is_idempotent(tmp_path):
    conn = _conn(tmp_path)
    tracker.mark_applied(conn, 1)
    tracker.mark_applied(conn, 1)
    assert conn.execute("SELECT COUNT(*) FROM application").fetchone()[0] == 1


def test_save_job_parks_at_saved_without_applied_at(tmp_path):
    conn = _conn(tmp_path)
    app = tracker.save_job(conn, 2)
    assert app["stage"] == "saved"
    assert app["applied_at"] is None


def test_advance_stage_moves_and_stamps_updated_at(tmp_path):
    conn = _conn(tmp_path)
    tracker.mark_applied(conn, 1)
    app = tracker.advance_stage(conn, 1, "round_1")
    assert app["stage"] == "round_1"
    assert app["updated_at"] is not None


def test_advance_stage_accepts_stages_the_way_people_say_them(tmp_path):
    # This is a voice-first app: nobody says "round_2" out loud.
    conn = _conn(tmp_path)
    for spoken, expected in [("round two", "round_2"), ("Round 1", "round_1"),
                             ("round-2", "round_2"), ("  FINAL ", "final"),
                             ("interviewing", "screening")]:
        app = tracker.advance_stage(conn, 1, spoken)
        assert app["stage"] == expected, f"{spoken!r} should map to {expected!r}"


def test_advance_stage_accepts_a_phase_named_with_the_word_round(tmp_path):
    # "Move it to the screening round" is how this is said out loud, and it was
    # rejected as an unknown stage: "screening round" joined to
    # "screening_round", which is not a stage. The user's request was dropped
    # and the agent asked them to pick a different word instead.
    conn = _conn(tmp_path)
    for spoken, expected in [("Screening Round", "screening"),
                             ("interview round", "screening"),
                             ("final round", "final"),
                             ("offer stage", "offer")]:
        app = tracker.advance_stage(conn, 1, spoken)
        assert app["stage"] == expected, f"{spoken!r} should map to {expected!r}"


def test_advance_stage_accepts_a_numbered_round_in_either_order(tmp_path):
    conn = _conn(tmp_path)
    for spoken, expected in [("round one", "round_1"), ("first round", "round_1"),
                             ("second round", "round_2"), ("round 2", "round_2")]:
        app = tracker.advance_stage(conn, 1, spoken)
        assert app["stage"] == expected, f"{spoken!r} should map to {expected!r}"


def test_the_word_round_alone_is_still_too_vague_to_act_on(tmp_path):
    assert tracker.normalise_stage("round") is None


def test_advance_stage_rejects_unknown_stage(tmp_path):
    conn = _conn(tmp_path)
    tracker.mark_applied(conn, 1)
    with pytest.raises(ValueError, match="Unknown stage"):
        tracker.advance_stage(conn, 1, "interviewed_maybe")


def test_advance_stage_starts_tracking_an_untracked_job(tmp_path):
    # The card's status dropdown can set any stage on a job the user never
    # explicitly saved or applied to, so staging has to create the row.
    conn = _conn(tmp_path)
    app = tracker.advance_stage(conn, 3, "round_1")
    assert app["stage"] == "round_1"
    assert app["job_id"] == 3


def test_advance_stage_stamps_applied_at_when_created_past_applied(tmp_path):
    conn = _conn(tmp_path)
    app = tracker.advance_stage(conn, 3, "screening")
    assert app["applied_at"] is not None


def test_advance_stage_leaves_applied_at_null_when_created_at_saved(tmp_path):
    conn = _conn(tmp_path)
    app = tracker.advance_stage(conn, 3, "saved")
    assert app["applied_at"] is None


def test_advance_stage_moves_backward_to_correct_a_mistake(tmp_path):
    # Unlike the monotonic _upsert path, an explicit stage change is the user
    # correcting the record and must be allowed to regress.
    conn = _conn(tmp_path)
    tracker.advance_stage(conn, 1, "round_2")
    app = tracker.advance_stage(conn, 1, "applied")
    assert app["stage"] == "applied"


def test_list_applications_expands_the_interviewing_pseudo_stage(tmp_path):
    conn = _conn(tmp_path)
    tracker.mark_applied(conn, 1)
    tracker.advance_stage(conn, 1, "round_2")
    tracker.mark_applied(conn, 2)
    assert [a["job_id"] for a in tracker.list_applications(conn, "interviewing")] == [1]


def test_pipeline_summary_counts_by_stage(tmp_path):
    conn = _conn(tmp_path)
    tracker.mark_applied(conn, 1)
    tracker.mark_applied(conn, 2)
    tracker.advance_stage(conn, 2, "round_1")
    s = tracker.pipeline_summary(conn)
    assert "1 applied" in s and "1 round 1" in s


def test_pipeline_summary_handles_empty_pipeline(tmp_path):
    assert "nothing" in tracker.pipeline_summary(_conn(tmp_path)).lower()


# Fix round 1 regression tests
def test_mark_applied_does_not_regress_job_already_in_round_2(tmp_path):
    """Verify mark_applied doesn't move job back from round_2 to applied."""
    conn = _conn(tmp_path)
    tracker.mark_applied(conn, 1)
    tracker.advance_stage(conn, 1, "round_2")
    app_before = tracker._get(conn, 1)
    assert app_before["stage"] == "round_2"

    # Calling mark_applied again should not regress the stage
    app_after = tracker.mark_applied(conn, 1)
    assert app_after["stage"] == "round_2", "mark_applied regressed stage from round_2 to applied"


def test_save_job_does_not_regress_job_already_in_round_2(tmp_path):
    """Verify save_job doesn't move job back from round_2 to saved."""
    conn = _conn(tmp_path)
    tracker.mark_applied(conn, 1)
    tracker.advance_stage(conn, 1, "round_2")
    app_before = tracker._get(conn, 1)
    assert app_before["stage"] == "round_2"

    # Calling save_job on an already-progressed job should not regress the stage
    app_after = tracker.save_job(conn, 1)
    assert app_after["stage"] == "round_2", "save_job regressed stage from round_2 to saved"


def test_mark_applied_still_works_on_fresh_untracked_job(tmp_path):
    """Verify mark_applied still correctly advances a fresh untracked job."""
    conn = _conn(tmp_path)
    app = tracker.mark_applied(conn, 2)
    assert app["stage"] == "applied"
    assert app["applied_at"] is not None


def test_save_job_still_works_on_fresh_untracked_job(tmp_path):
    """Verify save_job still correctly creates a fresh application row."""
    conn = _conn(tmp_path)
    app = tracker.save_job(conn, 3)
    assert app["stage"] == "saved"
    assert app["applied_at"] is None
