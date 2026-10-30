import pytest
from viktor_mcp_worker.settings import BridgeSettings


def test_settings_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIKTOR_MCP_SERVER_URL", "http://localhost:9000/mcp")
    monkeypatch.setenv("VIKTOR_MCP_BRIDGE_HOST", "localhost")
    monkeypatch.setenv("VIKTOR_MCP_BRIDGE_PORT", "9876")
    monkeypatch.setenv("VIKTOR_MCP_TOOL_CACHE_TTL_SECONDS", "12")

    settings = BridgeSettings.from_environment()

    assert settings.mcp_url == "http://localhost:9000/mcp"
    assert settings.execute_url == "http://localhost:9876/execute"
    assert settings.tool_cache_ttl_seconds == 12


def test_settings_reject_invalid_port() -> None:
    with pytest.raises(ValueError, match="between 1 and 65535"):
        BridgeSettings(port=0).validate()
