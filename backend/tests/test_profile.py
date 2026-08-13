import json
from core.db import connect, init_db
from core.profile import save_profile, get_profile, build_profile_prompt, PROFILE_SCHEMA


def _conn(tmp_path):
    c = connect(str(tmp_path / "t.db"))
    init_db(c)
    return c


def test_save_and_get_profile_roundtrips_json_columns(tmp_path):
    conn = _conn(tmp_path)
    pid = save_profile(conn, {
        "full_name": "Farha Jebin",
        "email": "f@example.com",
        "years_experience": 4.0,
        "seniority": "mid",
        "skills": ["Python", "React"],
        "titles": ["Backend Engineer"],
        "locations": ["Chennai"],
    }, raw_text="resume text")
    assert pid > 0
    p = get_profile(conn)
    assert p["full_name"] == "Farha Jebin"
    assert p["skills"] == ["Python", "React"]
    assert p["locations"] == ["Chennai"]


def test_get_profile_returns_none_when_empty(tmp_path):
    assert get_profile(_conn(tmp_path)) is None


def test_get_profile_returns_most_recent(tmp_path):
    conn = _conn(tmp_path)
    save_profile(conn, {"full_name": "First", "email": "", "years_experience": 1,
                        "seniority": "junior", "skills": [], "titles": [],
                        "locations": []}, raw_text="a")
    save_profile(conn, {"full_name": "Second", "email": "", "years_experience": 2,
                        "seniority": "mid", "skills": [], "titles": [],
                        "locations": []}, raw_text="b")
    assert get_profile(conn)["full_name"] == "Second"


def test_prompt_embeds_resume_text():
    assert "SOME RESUME" in build_profile_prompt("SOME RESUME")


def test_schema_requires_every_profile_field():
    assert set(PROFILE_SCHEMA["required"]) == {
        "full_name", "email", "years_experience", "seniority",
        "skills", "titles", "locations",
    }
