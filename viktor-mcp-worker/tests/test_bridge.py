import asyncio
from typing import Any

import pytest
from viktor_mcp_worker.bridge import MCPBridge


class FakeMCPResult:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def model_dump(self, **_kwargs: Any) -> dict[str, Any]:
        return self.payload


class FakeSession:
    def __init__(self) -> None:
        self.list_count = 0
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def list_tools(self) -> FakeMCPResult:
        self.list_count += 1
        return FakeMCPResult(
            {"tools": [{"name": "mock_tool", "inputSchema": {"type": "object"}}]}
        )

    async def call_tool(self, name: str, *, arguments: dict[str, Any]) -> FakeMCPResult:
        self.calls.append((name, arguments))
        if name == "fails":
            raise RuntimeError("mock failure")
        return FakeMCPResult({"content": [{"type": "text", "text": name}]})


class TestBridge(MCPBridge):
    __test__ = False

    def __init__(self, session: FakeSession) -> None:
        super().__init__(mcp_url="http://localhost:8000/mcp", tool_cache_ttl_seconds=60)
        self.fake_session = session

    async def _get_session(self) -> Any:
        return self.fake_session


@pytest.mark.asyncio
async def test_list_tools_uses_cache() -> None:
    session = FakeSession()
    bridge = TestBridge(session)

    first = await bridge.list_tools()
    second = await bridge.list_tools()

    assert first["cached"] is False
    assert second["cached"] is True
    assert session.list_count == 1


@pytest.mark.asyncio
async def test_force_refresh_reloads_tools() -> None:
    session = FakeSession()
    bridge = TestBridge(session)

    await bridge.list_tools()
    refreshed = await bridge.list_tools(force_refresh=True)

    assert refreshed["cached"] is False
    assert session.list_count == 2


@pytest.mark.asyncio
async def test_batch_keeps_individual_tool_errors() -> None:
    session = FakeSession()
    bridge = TestBridge(session)

    response = await bridge.call_tool_batch(
        tool_calls=[
            {"name": "works", "arguments": {"value": 1}},
            {"name": "fails", "arguments": {}},
            {"name": "bad_arguments", "arguments": []},
            {},
        ]
    )

    results = response["results"]
    assert [result["status"] for result in results] == [
        "success",
        "error",
        "error",
        "error",
    ]
    assert results[1]["error"]["message"] == "mock failure"
    assert session.calls == [("works", {"value": 1}), ("fails", {})]


@pytest.mark.asyncio
async def test_execute_rejects_unknown_operation() -> None:
    bridge = TestBridge(FakeSession())

    with pytest.raises(ValueError, match="Unsupported operation"):
        await bridge.execute({"operation": "unknown"})


@pytest.mark.asyncio
async def test_dispatcher_executes_and_stops_on_owner_task() -> None:
    bridge = TestBridge(FakeSession())
    owner_task = asyncio.create_task(bridge.serve())

    response = await bridge.submit({"operation": "health.check"})
    await bridge.stop()
    await owner_task

    assert response["status"] == "success"
    assert response["result"]["bridge"] == "ok"
