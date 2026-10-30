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
    build_tool_arguments,
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


def test_parse_worker_result_requires_success_and_tools_call():
    ok = {"status": "success", "operation": "tools.call", "result": {"structuredContent": {"a": 1}}}
    assert parse_worker_result(ok) == {"a": 1}
    with pytest.raises(RevitWorkerError):
        parse_worker_result({**ok, "status": "error"})
    with pytest.raises(RevitWorkerError):
        parse_worker_result({**ok, "operation": "tools.list"})
    with pytest.raises(RevitWorkerError):
        parse_worker_result("nope")


def test_build_tool_arguments_wraps_request_only_for_request_tools():
    assert build_tool_arguments("list_categories", {"includeEmpty": True}) == {
        "request": {"includeEmpty": True}
    }
    assert build_tool_arguments("list_categories", None) == {"request": {}}
    assert build_tool_arguments("get_model_name", None) == {}
    with pytest.raises(RevitWorkerError):
        build_tool_arguments("get_model_name", {"x": 1})


class FakeAnalysis:
    instances: ClassVar[list] = []

    def __init__(self, *, files, executable_key, output_filenames):
        self.files = files
        self.executable_key = executable_key
        self.output_filenames = output_filenames
        self.timeout = None
        self.instances.append(self)

    def execute(self, *, timeout):
        self.timeout = timeout

    def get_output_file(self, filename):
        assert filename == RESULT_FILE
        payload = {
            "status": "success",
            "operation": "tools.call",
            "result": {"structuredContent": {"title": "Demo"}},
        }
        return BytesIO(json.dumps(payload).encode())


async def test_call_tool_builds_request_file_and_parses_result():
    FakeAnalysis.instances.clear()
    with patch.object(worker_client, "GenericAnalysis", FakeAnalysis):
        result = await RevitWorkerClient().call_tool("get_model_name")

    assert result == {"title": "Demo"}
    analysis = FakeAnalysis.instances[0]
    assert analysis.executable_key == "mcp_bridge"
    assert analysis.timeout == 210
    name, handle = analysis.files[0]
    sent = json.loads(handle.getvalue())
    assert name == "request.json"
    assert sent["operation"] == "tools.call"
    assert sent["tool"] == {"name": "get_model_name", "arguments": {}}


async def test_call_tool_rejects_tools_outside_the_allow_list():
    with pytest.raises(RevitWorkerError, match="not allowed"):
        await RevitWorkerClient().call_tool("execute_revit_code")


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
