import json

import pytest
from agent.context import AgentContext
from state.results import read_result, save_result, stored_tool_names
from state.tables import read_table
from tools import mcp_tools
from tools.mcp_tools import (
    INLINE_LIMIT_BYTES,
    load_mcp_tools,
    make_mcp_tool,
    summarize_result,
)
from tools.viktor_tools import run_show_table, viktor_tools
from tools.worker_client import RevitWorkerError

from tests.test_tables import FakeStorage

LIST_CATEGORIES = {
    "name": "list_categories",
    "description": "List categories.",
    "inputSchema": {"type": "object", "properties": {"request": {"type": "object"}}},
    "annotations": {"readOnlyHint": True},
}
GET_MODEL_NAME = {"name": "get_model_name", "annotations": {"readOnlyHint": True}}
WRITER = {"name": "delete_everything", "annotations": {"readOnlyHint": False}}
RESULT = {"modelTitle": "Demo", "categories": [{"name": "Walls", "elementCount": 12}]}


class FakeClient:
    def __init__(self, tools=None, result=None, error=None):
        self.tools, self.result, self.error, self.calls = tools or [], result, error, []

    async def list_tools(self):
        if self.error:
            raise self.error
        return self.tools

    async def call_tool(self, name, arguments=None):
        self.calls.append((name, arguments))
        if self.error:
            raise self.error
        return self.result


class Ctx:
    context = AgentContext(storage_prefix="p")


@pytest.fixture(autouse=True)
def _fresh_cache(monkeypatch):
    mcp_tools.clear_tools_cache()
    monkeypatch.delenv(mcp_tools.ALLOW_WRITE_ENV, raising=False)


async def test_tools_are_built_from_the_server_list_and_hide_write_tools():
    client = FakeClient(tools=[LIST_CATEGORIES, GET_MODEL_NAME, WRITER])
    tools, warning = await load_mcp_tools(client)
    assert warning is None
    assert {t.name for t in tools} == {"list_categories", "get_model_name"}
    schema = next(t for t in tools if t.name == "list_categories").params_json_schema
    assert "request" in schema["properties"]  # the schema comes from the server


async def test_write_tools_need_explicit_opt_in(monkeypatch):
    monkeypatch.setenv(mcp_tools.ALLOW_WRITE_ENV, "true")
    tools, _ = await load_mcp_tools(FakeClient(tools=[WRITER]))
    assert [t.name for t in tools] == ["delete_everything"]


async def test_server_tool_cannot_shadow_an_app_tool():
    shadow = {"name": "show_table", "annotations": {"readOnlyHint": True}}
    tools, warning = await load_mcp_tools(FakeClient(tools=[shadow]))
    assert tools == []
    assert warning


async def test_unreachable_server_gives_a_warning_not_a_crash():
    client = FakeClient(error=RevitWorkerError("bridge down"))
    tools, warning = await load_mcp_tools(client)
    assert tools == []
    assert "bridge down" in warning


async def test_invoking_a_tool_stores_the_full_result_and_returns_json():
    storage, client = FakeStorage(), FakeClient(result=RESULT)
    tool = make_mcp_tool(LIST_CATEGORIES, client=client, storage=storage)

    raw = await tool.on_invoke_tool(Ctx(), '{"request": {"includeEmpty": true}}')
    out = json.loads(raw)

    assert out["status"] == "ok"
    assert out["data"] == RESULT
    assert client.calls == [("list_categories", {"request": {"includeEmpty": True}})]
    assert read_result("p", "list_categories", storage)["result"] == RESULT
    assert read_result("p", None, storage)["tool"] == "list_categories"  # "latest"


async def test_bad_json_and_unavailable_revit_return_tool_errors():
    client = FakeClient(error=RevitWorkerError("x"))
    tool = make_mcp_tool(LIST_CATEGORIES, client=client, storage=FakeStorage())
    bad_json = json.loads(await tool.on_invoke_tool(Ctx(), "{oops"))
    unavailable = json.loads(await tool.on_invoke_tool(Ctx(), "{}"))
    assert bad_json["errorType"] == "validation_error"
    assert unavailable["errorType"] == "revit_unavailable"


def test_large_results_are_previewed_for_the_llm():
    big = {"items": [{"n": i, "pad": "x" * 100} for i in range(500)], "total": 500}
    summary = summarize_result(big)
    assert summary["truncated"] is True
    assert summary["preview"]["items"]["count"] == 500
    assert len(summary["preview"]["items"]["firstItems"]) == 5
    assert len(json.dumps(summary)) < INLINE_LIMIT_BYTES
    assert summarize_result(RESULT) == RESULT  # small results are untouched


def test_show_table_reads_storage_and_fills_the_table():
    storage = FakeStorage()
    save_result("p", "list_categories", {}, RESULT, storage)

    out = json.loads(run_show_table("p", sort_by="elementCount", storage=storage))

    assert out["status"] == "ok"
    assert out["data"]["source"] == "list_categories"
    table = read_table("p", storage=storage)
    assert table["columns"] == ["Name", "Element count"]
    assert table["rows"] == [["Walls", 12]]
    assert stored_tool_names("p", storage) == ["list_categories"]


def test_show_table_errors_are_readable():
    storage = FakeStorage()
    missing = json.loads(run_show_table("p", storage=storage))
    assert missing["errorType"] == "no_stored_result"

    save_result("p", "t", {}, RESULT, storage)
    bad = json.loads(run_show_table("p", columns=["zzz"], storage=storage))
    assert bad["errorType"] == "table_error"


def test_app_owned_tools():
    assert {t.name for t in viktor_tools()} == {"report_progress", "show_table"}
