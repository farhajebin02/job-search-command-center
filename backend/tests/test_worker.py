from agent.worker import _resolve_workspace_mcp_user_email


def test_workspace_mcp_user_email_defaults_to_the_known_account(monkeypatch):
    monkeypatch.delenv("WORKSPACE_MCP_USER_EMAIL", raising=False)
    assert _resolve_workspace_mcp_user_email() == "farhajebin02@gmail.com"


def test_workspace_mcp_user_email_respects_an_override(monkeypatch):
    monkeypatch.setenv("WORKSPACE_MCP_USER_EMAIL", "someone-else@example.com")
    assert _resolve_workspace_mcp_user_email() == "someone-else@example.com"
