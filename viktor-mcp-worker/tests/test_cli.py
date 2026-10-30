import json
from pathlib import Path

from viktor_mcp_worker.cli import MCPBridgeCLI
from viktor_mcp_worker.settings import BridgeSettings


def test_cli_writes_error_when_request_is_missing(tmp_path: Path) -> None:
    exit_code = MCPBridgeCLI(BridgeSettings(), workdir=tmp_path).run()

    result = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    assert exit_code == 0
    assert result["status"] == "error"
    assert result["error"]["type"] == "FileNotFoundError"


def test_cli_rejects_non_object_request(tmp_path: Path) -> None:
    (tmp_path / "request.json").write_text("[]", encoding="utf-8")

    MCPBridgeCLI(BridgeSettings(), workdir=tmp_path).run()

    result = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    assert result["error"]["type"] == "ValueError"
