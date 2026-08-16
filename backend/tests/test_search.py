from core.db import connect, init_db
from core import search, tracker


def _conn(tmp_path):
    c = connect(str(tmp_path / "t.db"))
    init_db(c)
    c.execute("INSERT INTO job (source, source_id, title, company, location, "
              "apply_url) VALUES ('seed','s1','Backend Engineer','Freshworks','Chennai','u')")
    c.execute("INSERT INTO job (source, source_id, title, company, location, "
              "apply_url) VALUES ('seed','s2','Data Analyst','Zoho','Chennai','u')")
    c.commit()
    return c


def test_find_jobs_matches_company_case_insensitively(tmp_path):
    r = search.find_jobs(_conn(tmp_path), "freshworks")
    assert [j["company"] for j in r] == ["Freshworks"]


def test_find_jobs_matches_title_substring(tmp_path):
    r = search.find_jobs(_conn(tmp_path), "analyst")
    assert [j["title"] for j in r] == ["Data Analyst"]


def test_find_jobs_matches_a_stage_name(tmp_path):
    conn = _conn(tmp_path)
    tracker.mark_applied(conn, 1)
    tracker.advance_stage(conn, 1, "round_2")
    r = search.find_jobs(conn, "round 2")
    assert [j["id"] for j in r] == [1]


def test_find_jobs_attaches_stage_when_tracked(tmp_path):
    conn = _conn(tmp_path)
    tracker.mark_applied(conn, 1)
    assert search.find_jobs(conn, "freshworks")[0]["stage"] == "applied"


def test_find_jobs_returns_empty_for_no_match(tmp_path):
    assert search.find_jobs(_conn(tmp_path), "quantum welder") == []


def test_find_jobs_matches_a_title_and_company_said_together(tmp_path):
    # People name jobs the way they'd say them out loud. Matching the whole
    # phrase against one column can never hit: the title holds half of it and
    # the company the other half.
    r = search.find_jobs(_conn(tmp_path), "Backend Engineer at Freshworks")
    assert [j["company"] for j in r] == ["Freshworks"]


def test_find_jobs_ignores_filler_words(tmp_path):
    r = search.find_jobs(_conn(tmp_path), "the data analyst job")
    assert [j["title"] for j in r] == ["Data Analyst"]


def test_find_jobs_requires_every_term_to_match(tmp_path):
    # "Analyst at Freshworks" must not return the Zoho analyst just because
    # one word happened to land.
    assert search.find_jobs(_conn(tmp_path), "Analyst at Freshworks") == []


def test_find_jobs_of_only_filler_returns_nothing(tmp_path):
    assert search.find_jobs(_conn(tmp_path), "the job") == []


# Speech-to-text does not spell company names the way the database does. These
# cover the drift: the transcript says "Senas" and the row says "Sanas", or the
# name comes back mangled past recognition and only the rest of the phrase is
# usable. Both used to return nothing at all.
def _stt_conn(tmp_path):
    c = _conn(tmp_path)
    c.execute("INSERT INTO job (source, source_id, title, company, location, "
              "apply_url) VALUES ('seed','s3','Software Engineering Intern - SI "
              "& Agentic AI Platform','Sanas','Remote','u')")
    c.execute("INSERT INTO job (source, source_id, title, company, location, "
              "apply_url) VALUES ('seed','s4','AI Intern','Evnek Technologies "
              "Pvt Ltd','Chennai','u')")
    c.commit()
    return c


def test_find_jobs_tolerates_a_misheard_company_name(tmp_path):
    # Heard as "Senas", stored as "Sanas" — one substituted letter in five.
    r = search.find_jobs(_stt_conn(tmp_path), "Senas Software Engineer Intern")
    assert [j["company"] for j in r] == ["Sanas"]


def test_a_misheard_name_still_counts_as_an_exact_match(tmp_path):
    # Every term landed, one of them fuzzily. The agent should act on it, not
    # hedge, so it must not be flagged as a guess.
    r = search.find_jobs(_stt_conn(tmp_path), "Senas Software Engineer Intern")
    assert r[0]["exact"] is True


def test_find_jobs_offers_near_matches_when_the_name_is_unrecognisable(tmp_path):
    # "Evnek" came back as "Evana". No fuzzy threshold saves that, but three of
    # the four terms still point at exactly one job.
    r = search.find_jobs(_stt_conn(tmp_path), "Evana Technologies AI Intern")
    assert [j["company"] for j in r] == ["Evnek Technologies Pvt Ltd"]


def test_near_matches_are_flagged_so_the_agent_can_confirm_first(tmp_path):
    r = search.find_jobs(_stt_conn(tmp_path), "Evana Technologies AI Intern")
    assert r[0]["exact"] is False


def test_exact_matches_are_flagged_as_certain(tmp_path):
    r = search.find_jobs(_conn(tmp_path), "Backend Engineer at Freshworks")
    assert r[0]["exact"] is True


def test_an_exact_match_suppresses_the_near_ones(tmp_path):
    # Naming a job precisely must not drag in everything that shares a word.
    r = search.find_jobs(_stt_conn(tmp_path), "Data Analyst at Zoho")
    assert [j["company"] for j in r] == ["Zoho"]


def test_one_stray_word_out_of_several_is_not_a_near_match(tmp_path):
    # "Analyst at Freshworks" names no real job. Returning the Zoho analyst
    # because one word landed is how the wrong row gets updated.
    assert search.find_jobs(_stt_conn(tmp_path), "Analyst at Freshworks") == []


def test_fuzzy_matching_does_not_fire_on_short_words(tmp_path):
    # Two- and three-letter terms are close to half the dictionary. "ml" must
    # not drag in "AI" roles.
    assert search.find_jobs(_stt_conn(tmp_path), "ml") == []
