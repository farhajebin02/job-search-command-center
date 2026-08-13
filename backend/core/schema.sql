CREATE TABLE IF NOT EXISTS profile (
  id INTEGER PRIMARY KEY, full_name TEXT, email TEXT,
  years_experience REAL, seniority TEXT, skills_json TEXT,
  titles_json TEXT, locations_json TEXT, raw_text TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS job (
  id INTEGER PRIMARY KEY, source TEXT, source_id TEXT, title TEXT,
  company TEXT, location TEXT, description TEXT, salary_min REAL,
  salary_max REAL, apply_url TEXT, posted_at TEXT, fetched_at TEXT,
  UNIQUE(source, source_id)
);
CREATE TABLE IF NOT EXISTS match (
  id INTEGER PRIMARY KEY, job_id INTEGER, profile_id INTEGER,
  score INTEGER, matched_skills_json TEXT, gaps_json TEXT,
  rationale TEXT, scored_at TEXT, UNIQUE(job_id, profile_id)
);
CREATE TABLE IF NOT EXISTS application (
  id INTEGER PRIMARY KEY, job_id INTEGER UNIQUE, stage TEXT,
  applied_at TEXT, updated_at TEXT, notes TEXT
);
CREATE TABLE IF NOT EXISTS interview (
  id INTEGER PRIMARY KEY, application_id INTEGER, round_label TEXT,
  scheduled_at TEXT, calendar_event_id TEXT, location TEXT, notes TEXT
);
CREATE TABLE IF NOT EXISTS mock_session (
  id INTEGER PRIMARY KEY, job_id INTEGER, started_at TEXT,
  ended_at TEXT, transcript TEXT, feedback_json TEXT
);
CREATE TABLE IF NOT EXISTS fetch_run (
  id INTEGER PRIMARY KEY, query TEXT, source TEXT,
  ran_at TEXT, job_ids_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_job_company ON job(company);
CREATE INDEX IF NOT EXISTS idx_application_stage ON application(stage);
