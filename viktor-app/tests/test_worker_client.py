import json
from io import BytesIO
from typing import ClassVar
from unittest.mock import patch

import pytest
from tools import worker_client
from tools.worker_client import (
    RESULT_FILE,
    RevitWorkerClient,
    RevitWorkerError,
    parse_tool_result,
    parse_worker_result,
)


class Value:
    def __init__(self, text):
        self.text = text


class Result:
    def __init__(self, *, structured=None, content=None, error=False):
        self.structuredContent = structured
        self.content = content or []
        self.isError = error


def test_parse_tool_result_prefers_structured_content():
    assert parse_tool_result(Result(structured={"title": "A"})) == {"title": "A"}


def test_parse_tool_result_reads_single_json_text():
    result = Result(content=[Value('{"title": "B"}')])
    assert parse_tool_result(result) == {"title": "B"}


@pytest.mark.parametrize(
    "result",
    [
        Result(error=True),
        Result(content=[]),
        Result(content=[Value("not json")]),
        Result(content=[Value("[1, 2]")]),
        Result(structured=[1]),
    ],
)
def test_parse_tool_result_rejects_bad_results(result):
    with pytest.raises(RevitWorkerError):
        parse_tool_result(result)


def test_parse_worker_result_checks_status_and_operation():
    ok = {"status": "success", "operation": "tools.call", "result": {"a": 1}}
    assert parse_worker_result(ok, "tools.call") == {"a": 1}
    with pytest.raises(RevitWorkerError):
        parse_worker_result({**ok, "status": "error"}, "tools.call")
    with pytest.raises(RevitWorkerError):
        parse_worker_result(ok, "tools.list")
    with pytest.raises(RevitWorkerError):
        parse_worker_result("nope", "tools.call")


class FakeAnalysis:
    """Stands in for GenericAnalysis; answers according to the operation requested."""

    instances: ClassVar[list] = []

    def __init__(self, *, files, executable_key, output_filenames):
        self.request = json.loads(files[0][1].getvalue())
        self.executable_key = executable_key
        self.timeout = None
        self.instances.append(self)

    def execute(self, *, timeout):
        self.timeout = timeout

    def get_output_file(self, filename):
        assert filename == RESULT_FILE
        if self.request["operation"] == "tools.list":
            result = {"tools": [{"name": "get_model_name"}]}
        else:
            result = {"structuredContent": {"title": "Demo"}}
        payload = {
            "status": "success",
            "operation": self.request["operation"],
            "result": result,
        }
        return BytesIO(json.dumps(payload).encode())


async def test_call_tool_passes_arguments_through_unchanged():
    FakeAnalysis.instances.clear()
    with patch.object(worker_client, "GenericAnalysis", FakeAnalysis):
        result = await RevitWorkerClient().call_tool(
            "list_categories", {"request": {"includeEmpty": True}}
        )

    assert result == {"title": "Demo"}
    analysis = FakeAnalysis.instances[0]
    assert analysis.executable_key == "mcp_bridge"
    assert analysis.timeout == 210
    assert analysis.request["tool"] == {
        "name": "list_categories",
        "arguments": {"request": {"includeEmpty": True}},
    }


async def test_list_tools_returns_server_definitions():
    with patch.object(worker_client, "GenericAnalysis", FakeAnalysis):
        tools = await RevitWorkerClient().list_tools()
    assert tools == [{"name": "get_model_name"}]


async def test_call_tool_converts_worker_failures():
    class Boom(FakeAnalysis):
        def execute(self, *, timeout):
            raise ConnectionError("worker offline")

    with (
        patch.object(worker_client, "GenericAnalysis", Boom),
        pytest.raises(RevitWorkerError, match="Could not run"),
    ):
        await RevitWorkerClient().call_tool("get_model_name")


def test_from_env_rejects_empty_executable_key(monkeypatch):
    monkeypatch.setenv("VIKTOR_MCP_WORKER_EXECUTABLE_KEY", "  ")
    with pytest.raises(RevitWorkerError):
        RevitWorkerClient.from_env()
