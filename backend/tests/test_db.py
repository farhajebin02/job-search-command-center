from core.db import connect, init_db


def test_init_db_creates_all_tables(tmp_path):
    conn = connect(str(tmp_path / "t.db"))
    init_db(conn)
    names = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert {"profile", "job", "match", "application",
            "interview", "mock_session", "fetch_run"} <= names


def test_init_db_is_idempotent(tmp_path):
    conn = connect(str(tmp_path / "t.db"))
    init_db(conn)
    init_db(conn)  # must not raise


def test_wal_mode_is_enabled(tmp_path):
    conn = connect(str(tmp_path / "t.db"))
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
