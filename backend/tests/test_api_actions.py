import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("LIVEKIT_API_KEY", "devkey")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "devsecretdevsecretdevsecret")
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")
    from api.main import create_app
    from core.db import connect
    app = create_app()
    c = connect(str(tmp_path / "t.db"))
    c.execute("INSERT INTO job (source, source_id, title, company, location, "
              "apply_url) VALUES ('seed','s1','Backend Engineer','Freshworks','Chennai','u')")
    c.commit()
    return TestClient(app)


def test_apply_endpoint_moves_job_to_applied(client):
    r = client.post("/api/applications/1/apply")
    assert r.status_code == 200
    assert r.json()["application"]["stage"] == "applied"
    assert any(a["stage"] == "applied"
               for a in client.get("/api/applications").json()["applications"])


def test_stage_endpoint_rejects_unknown_stage(client):
    client.post("/api/applications/1/apply")
    r = client.post("/api/applications/1/stage", json={"stage": "nope"})
    assert r.status_code == 400


def test_stage_endpoint_tracks_a_job_that_was_never_applied_to(client):
    # The status dropdown on a job card posts straight here, so a job the user
    # never marked applied must not come back as a 400.
    r = client.post("/api/applications/1/stage", json={"stage": "screening"})
    assert r.status_code == 200
    assert r.json()["application"]["stage"] == "screening"
    assert any(a["stage"] == "screening"
               for a in client.get("/api/applications").json()["applications"])


def test_search_endpoint_finds_by_company(client):
    r = client.get("/api/search", params={"q": "freshworks"})
    assert [j["company"] for j in r.json()["jobs"]] == ["Freshworks"]


def test_applications_endpoint_filters_by_stage(client):
    client.post("/api/applications/1/apply")

    # Seed a second job and park it at a different stage — without this,
    # the ?stage=applied filter is never actually exercised: the DB would
    # contain exactly one application either way, so a broken/deleted
    # filter would pass this test identically.
    from core.db import connect
    conn = connect()  # DB_PATH already set by the fixture's monkeypatch
    conn.execute("INSERT INTO job (source, source_id, title, company, location, "
                 "apply_url) VALUES ('seed','s2','Data Analyst','Zoho','Chennai','u')")
    conn.commit()
    client.post("/api/applications/2/apply")
    client.post("/api/applications/2/stage", json={"stage": "screening"})

    r = client.get("/api/applications", params={"stage": "applied"})
    apps = r.json()["applications"]
    assert len(apps) == 1
    assert apps[0]["job_id"] == 1
    assert all(a["stage"] == "applied" for a in apps)
