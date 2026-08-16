import pytest
from core.db import connect, init_db
from core import interviews, tracker


def _conn(tmp_path):
    c = connect(str(tmp_path / "t.db"))
    init_db(c)
    c.execute("INSERT INTO job (source, source_id, title, company, location, "
              "apply_url) VALUES ('seed','s1','Backend Engineer','Freshworks','Chennai','u')")
    c.commit()
    tracker.mark_applied(c, 1)
    return c


def test_record_interview_links_to_the_application(tmp_path):
    conn = _conn(tmp_path)
    iv = interviews.record_interview(conn, 1, "2026-08-18T15:00:00", "round_1", "evt-1")
    assert iv["round_label"] == "round_1"
    assert iv["calendar_event_id"] == "evt-1"


def test_record_interview_requires_a_tracked_job(tmp_path):
    conn = _conn(tmp_path)
    with pytest.raises(ValueError, match="not tracked"):
        interviews.record_interview(conn, 999, "2026-08-18T15:00:00", "round_1", None)


def test_set_calendar_event_backfills_the_id_after_the_event_is_created(tmp_path):
    # The row is written before Google is called, so that a failed calendar
    # write cannot cost the user the interview record. The id therefore
    # arrives second.
    conn = _conn(tmp_path)
    iv = interviews.record_interview(conn, 1, "2026-08-18T15:00:00", "round_1", None)

    interviews.set_calendar_event(conn, iv["id"], "evt-9")

    row = conn.execute("SELECT calendar_event_id FROM interview WHERE id=?",
                       (iv["id"],)).fetchone()
    assert row["calendar_event_id"] == "evt-9"


def test_upcoming_lists_future_interviews_with_job_details(tmp_path):
    conn = _conn(tmp_path)
    interviews.record_interview(conn, 1, "2099-01-01T10:00:00", "round_1", None)
    up = interviews.upcoming(conn)
    assert up[0]["company"] == "Freshworks"


def test_upcoming_excludes_past_interviews(tmp_path):
    conn = _conn(tmp_path)
    interviews.record_interview(conn, 1, "2020-01-01T10:00:00", "round_1", None)
    assert interviews.upcoming(conn) == []
