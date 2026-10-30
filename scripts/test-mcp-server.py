#!/usr/bin/env python3
import argparse
import asyncio
import json
import sys

try:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    from mcp.types import CallToolResult, TextContent
except ImportError as exc:
    print(
        "Missing dependency: install the official MCP Python SDK first.\n"
        "Suggested command: pip install mcp",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc


async def run(url: str, tool_name: str | None, tool_arguments: dict) -> int:
    async with (
        streamable_http_client(url) as (read_stream, write_stream, _),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()

        tools_result = await session.list_tools()
        tool_names = [tool.name for tool in tools_result.tools]

        print("Connected to MCP server")
        print(f"URL: {url}")
        print("Available tools:")
        for name in tool_names:
            print(f"  - {name}")

        if not tool_name:
            return 0

        print("")
        print(f"Calling tool: {tool_name}")
        print(f"Arguments: {json.dumps(tool_arguments)}")

        result = await session.call_tool(tool_name, arguments=tool_arguments)
        _print_tool_result(result)
        return 0


def _print_tool_result(result: CallToolResult) -> None:
    if result.structuredContent is not None:
        print("Structured content:")
        print(json.dumps(result.structuredContent, indent=2))

    if not result.content:
        print("No content returned.")
        return

    print("Content:")
    for item in result.content:
        if isinstance(item, TextContent):
            print(item.text)
        else:
            print(item.model_dump_json(indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke-test a Streamable HTTP MCP server."
    )
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:5099/mcp",
        help="Streamable HTTP MCP endpoint URL.",
    )
    parser.add_argument(
        "--tool",
        default=None,
        help="Optional tool name to call after listing tools.",
    )
    parser.add_argument(
        "--arguments",
        default="{}",
        help="JSON object string passed as tool arguments.",
    )
    args = parser.parse_args()

    try:
        tool_arguments = json.loads(args.arguments)
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON in --arguments: {exc}", file=sys.stderr)
        return 2

    if not isinstance(tool_arguments, dict):
        print("--arguments must decode to a JSON object.", file=sys.stderr)
        return 2

    try:
        return asyncio.run(run(args.url, args.tool, tool_arguments))
    except Exception as exc:  # pragma: no cover - best effort CLI script
        print(f"MCP test failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
