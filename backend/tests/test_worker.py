from agent.worker import _resolve_workspace_mcp_user_email, build_calendar_server


def test_workspace_mcp_user_email_defaults_to_the_known_account(monkeypatch):
    monkeypatch.delenv("WORKSPACE_MCP_USER_EMAIL", raising=False)
    assert _resolve_workspace_mcp_user_email() == "farhajebin02@gmail.com"


def test_workspace_mcp_user_email_respects_an_override(monkeypatch):
    monkeypatch.setenv("WORKSPACE_MCP_USER_EMAIL", "someone-else@example.com")
    assert _resolve_workspace_mcp_user_email() == "someone-else@example.com"


def test_calendar_server_requests_the_calendar_toolset():
    # Without --tools calendar the server still starts, but manage_event never
    # registers and every interview silently misses the user's calendar.
    assert "calendar" in build_calendar_server().args


def test_calendar_server_pins_the_google_account(monkeypatch):
    monkeypatch.setenv("WORKSPACE_MCP_USER_EMAIL", "someone-else@example.com")
    assert build_calendar_server().env["USER_GOOGLE_EMAIL"] == "someone-else@example.com"


def test_calendar_server_waits_long_enough_for_uvx_to_boot():
    # uvx workspace-mcp needs ~21s on this machine; the SDK default is 5s, and
    # expiring means the calendar tools never register at all.
    assert build_calendar_server()._read_timeout >= 30
