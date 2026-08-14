import io
import json

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("LIVEKIT_API_KEY", "devkey")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "devsecretdevsecretdevsecret")
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")
    from api.main import create_app
    return TestClient(create_app())


def _blank_pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_token_returns_jwt_and_url(client):
    r = client.get("/api/token", params={"identity": "u1", "room": "cmd"})
    assert r.status_code == 200
    body = r.json()
    assert body["token"].count(".") == 2
    assert body["url"] == "wss://example.livekit.cloud"
    assert body["room"] == "cmd"


def test_token_requires_identity(client):
    assert client.get("/api/token").status_code == 422


def test_jobs_is_empty_on_cold_start(client):
    assert client.get("/api/jobs").json() == {"jobs": []}


def test_upload_rejects_non_pdf(client):
    r = client.post("/api/upload",
                    files={"file": ("cv.txt", b"hello", "text/plain")})
    assert r.status_code == 400
    assert "PDF" in r.json()["detail"]


def test_upload_rejects_pdf_with_no_extractable_text(client):
    r = client.post("/api/upload",
                    files={"file": ("cv.pdf", _blank_pdf_bytes(), "application/pdf")})
    assert r.status_code == 400
    assert "PDF" in r.json()["detail"]


def test_applications_is_empty_on_cold_start(client):
    assert client.get("/api/applications").json() == {"applications": []}


def test_job_stage_is_none_then_reflects_application(client, tmp_path):
    from core.db import connect

    conn = connect(str(tmp_path / "t.db"))
    cur = conn.execute(
        """INSERT INTO job (source, source_id, title, company, location,
               description, apply_url, fetched_at)
           VALUES ('seed','1','Backend Engineer','Acme','Chennai',
               'Python role.','http://example.com/job/1','2026-08-14T00:00:00Z')"""
    )
    job_id = cur.lastrowid
    conn.execute(
        "INSERT INTO fetch_run (query, source, ran_at, job_ids_json) VALUES (?,?,?,?)",
        ("backend engineer | Chennai", "seed", "2026-08-14T00:00:00Z",
         json.dumps([job_id])),
    )
    conn.commit()

    r = client.get("/api/jobs")
    jobs = r.json()["jobs"]
    assert len(jobs) == 1
    assert jobs[0]["id"] == job_id
    assert jobs[0]["stage"] is None

    conn.execute(
        "INSERT INTO application (job_id, stage, applied_at, updated_at) "
        "VALUES (?, 'applied', ?, ?)",
        (job_id, "2026-08-14T00:00:00Z", "2026-08-14T00:00:00Z"),
    )
    conn.commit()

    r2 = client.get("/api/jobs")
    jobs2 = r2.json()["jobs"]
    assert jobs2[0]["stage"] == "applied"
