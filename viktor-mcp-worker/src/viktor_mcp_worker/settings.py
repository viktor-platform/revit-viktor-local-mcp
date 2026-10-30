import os
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True, slots=True)
class BridgeSettings:
    """Runtime settings for the local bridge service."""

    mcp_url: str = "http://127.0.0.1:8000/mcp"
    host: str = "127.0.0.1"
    port: int = 8765
    tool_cache_ttl_seconds: int = 300

    @classmethod
    def from_environment(cls) -> "BridgeSettings":
        settings = cls(
            mcp_url=os.environ.get(
                "VIKTOR_MCP_SERVER_URL", "http://127.0.0.1:8000/mcp"
            ),
            host=os.environ.get("VIKTOR_MCP_BRIDGE_HOST", "127.0.0.1"),
            port=int(os.environ.get("VIKTOR_MCP_BRIDGE_PORT", "8765")),
            tool_cache_ttl_seconds=int(
                os.environ.get("VIKTOR_MCP_TOOL_CACHE_TTL_SECONDS", "300")
            ),
        )
        settings.validate()
        return settings

    @property
    def execute_url(self) -> str:
        return f"http://{self.host}:{self.port}/execute"

    def validate(self) -> None:
        parsed_url = urlsplit(self.mcp_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("VIKTOR_MCP_SERVER_URL must be an HTTP(S) URL")
        if not self.host:
            raise ValueError("VIKTOR_MCP_BRIDGE_HOST cannot be empty")
        if not 1 <= self.port <= 65_535:
            raise ValueError("VIKTOR_MCP_BRIDGE_PORT must be between 1 and 65535")
        if self.tool_cache_ttl_seconds < 0:
            raise ValueError("VIKTOR_MCP_TOOL_CACHE_TTL_SECONDS cannot be negative")
