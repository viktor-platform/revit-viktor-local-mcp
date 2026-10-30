import json

from tools.revit_tools import (
    REVIT_UNAVAILABLE_HINT,
    build_agent_tools,
    run_get_model_name,
    run_list_categories,
)
from tools.worker_client import RevitWorkerError

from tests.test_tables import FakeStorage
from state.tables import read_table


class FakeClient:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    async def call_tool(self, name, request=None):
        self.calls.append((name, request))
        if self.error:
            raise self.error
        return self.result


CATEGORIES = {
    "modelTitle": "Demo",
    "categoryCount": 20,
    "totalElementCount": 999,
    "categories": [
        {"name": f"Cat {i}", "builtInCategory": f"OST_{i}", "categoryType": "Model", "elementCount": 100 - i}
        for i in range(20)
    ],
}


async def test_get_model_name_saves_table_and_returns_summary():
    storage = FakeStorage()
    client = FakeClient({"title": "Demo", "filePath": "", "isWorkshared": False, "revitVersion": "2027"})

    payload = json.loads(await run_get_model_name("p", client=client, storage=storage))

    assert payload["status"] == "ok"
    assert payload["data"]["title"] == "Demo"
    table = read_table("p", storage=storage)
    assert table["columns"] == ["Property", "Value"]
    assert ["Title", "Demo"] in table["rows"]
    assert ["File path", "(not saved yet)"] in table["rows"]
    assert client.calls == [("get_model_name", None)]


async def test_list_categories_stores_everything_but_summarises_for_the_llm():
    storage = FakeStorage()
    client = FakeClient(CATEGORIES)

    payload = json.loads(
        await run_list_categories("p", include_empty=True, client=client, storage=storage)
    )

    assert payload["status"] == "ok"
    assert len(payload["data"]["largestCategories"]) == 15  # LLM gets the top 15 only
    assert len(read_table("p", storage=storage)["rows"]) == 20  # table gets all 20
    assert client.calls == [
        ("list_categories", {"includeEmpty": True, "modelCategoriesOnly": True})
    ]


async def test_revit_unavailable_becomes_a_tool_error_without_touching_the_table():
    storage = FakeStorage()
    client = FakeClient(error=RevitWorkerError("bridge down"))

    for run in (run_get_model_name, run_list_categories):
        payload = json.loads(await run("p", client=client, storage=storage))
        assert payload["status"] == "error"
        assert payload["errorType"] == "revit_unavailable"
        assert payload["retryAction"] == REVIT_UNAVAILABLE_HINT

    assert read_table("p", storage=storage) is None


def test_agent_exposes_the_expected_tools():
    names = {tool.name for tool in build_agent_tools()}
    assert names == {"report_progress", "get_model_name", "list_categories"}
