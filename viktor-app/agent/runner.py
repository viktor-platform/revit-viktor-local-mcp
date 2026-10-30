import asyncio
import json
import queue
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import openai
import viktor as vkt
from agents import (
    Agent,
    ItemHelpers,
    MaxTurnsExceeded,
    ModelBehaviorError,
    ModelSettings,
    RunConfig,
    Runner,
    ToolExecutionConfig,
    set_default_openai_client,
    set_tracing_disabled,
)
from agents.items import TResponseInputItem
from openai import AsyncOpenAI
from openai.types.responses import ResponseTextDeltaEvent
from openai.types.shared import Reasoning
from tools.revit_tools import build_agent_tools

from agent.context import AgentContext

MODEL_NAME = "openai.gpt-oss-120b"
MAX_AGENT_TURNS = 50
EMPTY_RESPONSE = (
    "The agent finished without a final answer. Any tool results above are partial; "
    "check the Revit results table or ask again."
)
TOOL_DISPLAY_NAMES = {
    "get_model_name": "Get Model Name",
    "list_categories": "List Categories",
}
PROGRESS_TOOL_NAME = "report_progress"

_event_loop: asyncio.AbstractEventLoop | None = None
_event_loop_thread: threading.Thread | None = None


def configure_viktor_agents_client() -> None:
    client = AsyncOpenAI(
        base_url=vkt.ViktorOpenAI.get_base_url(version="v1"),
        api_key=vkt.ViktorOpenAI.get_api_key(),
    )
    set_default_openai_client(client, use_for_tracing=False)
    set_tracing_disabled(True)


def load_system_prompt() -> str:
    return (Path(__file__).resolve().parent / "system_prompt.xml").read_text(
        encoding="utf-8"
    )


def build_agent() -> Agent[AgentContext]:
    return Agent[AgentContext](
        name="Revit Model Assistant",
        model=MODEL_NAME,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium"),
            parallel_tool_calls=False,
        ),
        instructions=load_system_prompt(),
        tools=build_agent_tools(),
    )


def _ensure_event_loop() -> asyncio.AbstractEventLoop:
    global _event_loop, _event_loop_thread
    if _event_loop and _event_loop.is_running():
        return _event_loop
    _event_loop = asyncio.new_event_loop()
    _event_loop_thread = threading.Thread(
        target=_event_loop.run_forever,
        name="revit-agent-loop",
        daemon=True,
    )
    _event_loop_thread.start()
    return _event_loop


def _extract_call_id(raw: Any) -> str | None:
    if isinstance(raw, dict):
        value = raw.get("call_id") or raw.get("id") or raw.get("tool_call_id")
        return str(value) if value else None
    for attribute in ("call_id", "id", "tool_call_id"):
        value = getattr(raw, attribute, None)
        if value:
            return str(value)
    return None


def _extract_tool_name(raw: Any) -> str:
    if isinstance(raw, dict):
        if raw.get("name"):
            return str(raw["name"])
        function = raw.get("function")
        if isinstance(function, dict) and function.get("name"):
            return str(function["name"])
        if raw.get("tool_name"):
            return str(raw["tool_name"])
    for attribute in ("name", "tool_name", "function_name"):
        value = getattr(raw, attribute, None)
        if value:
            return str(value)
    function = getattr(raw, "function", None)
    if function is not None and getattr(function, "name", None):
        return str(function.name)
    return "tool"


def _extract_tool_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        arguments = raw.get("arguments")
        if arguments is None and isinstance(raw.get("function"), dict):
            arguments = raw["function"].get("arguments")
    else:
        arguments = getattr(raw, "arguments", None)
        if arguments is None:
            function = getattr(raw, "function", None)
            arguments = getattr(function, "arguments", None) if function else None
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _normalize_stream_text(text: str) -> str:
    return " ".join(text.split()).strip()


def _stream_error_message(exc: Exception) -> str:
    if isinstance(exc, MaxTurnsExceeded):
        return (
            "I could not finish within 50 tool turns. Try a narrower request."
        )
    if isinstance(exc, ModelBehaviorError):
        return (
            "The agent could not produce a valid final response. Any tool results "
            "above remain partial."
        )
    if isinstance(exc, openai.RateLimitError):
        return "VIKTOR LLM fair usage limit reached. Please try again later."
    if isinstance(exc, openai.APIConnectionError):
        return f"Could not reach the VIKTOR LLM service: {exc}"
    if isinstance(exc, openai.APIStatusError):
        return f"VIKTOR LLM API error {exc.status_code}: {exc.message}"
    return f"The agent stopped unexpectedly: {exc}"


def run_agent(
    chat_history: list[dict[str, str]], context: AgentContext
) -> Iterator[str]:
    output_queue: queue.Queue[object] = queue.Queue()
    sentinel = object()
    loop = _ensure_event_loop()

    async def produce() -> None:
        call_id_to_name: dict[str, str] = {}
        pending_assistant_message: str | None = None
        streamed_message_text = ""
        final_text_since_tool = False
        try:
            configure_viktor_agents_client()
            result = Runner.run_streamed(
                build_agent(),
                input=cast("list[TResponseInputItem]", chat_history),
                context=context,
                max_turns=MAX_AGENT_TURNS,
                run_config=RunConfig(
                    tool_execution=ToolExecutionConfig(max_function_tool_concurrency=1)
                ),
            )

            async for event in result.stream_events():
                if event.type == "raw_response_event" and isinstance(
                    event.data,
                    ResponseTextDeltaEvent,
                ):
                    if event.data.delta:
                        streamed_message_text += event.data.delta
                        if event.data.delta.strip():
                            final_text_since_tool = True
                        output_queue.put(event.data.delta)
                    continue

                if event.type != "run_item_stream_event":
                    continue

                item = event.item
                raw = getattr(item, "raw_item", None)

                if (
                    event.name == "message_output_created"
                    and getattr(item, "type", None) == "message_output_item"
                ):
                    message = ItemHelpers.text_message_output(
                        item  # ty: ignore[invalid-argument-type]
                    ).strip()
                    if message and _normalize_stream_text(
                        message
                    ) != _normalize_stream_text(streamed_message_text):
                        pending_assistant_message = message
                    else:
                        pending_assistant_message = None
                    streamed_message_text = ""
                    continue

                if event.name == "tool_called":
                    final_text_since_tool = False
                    if pending_assistant_message:
                        output_queue.put(f"\n\n{pending_assistant_message}\n\n")
                        pending_assistant_message = None
                    call_id = _extract_call_id(raw)
                    tool_name = _extract_tool_name(raw)
                    if call_id:
                        call_id_to_name[call_id] = tool_name
                    if tool_name == PROGRESS_TOOL_NAME:
                        message = str(_extract_tool_arguments(raw).get("message") or "")
                        message = " ".join(message.split()).strip()[:300]
                        if message:
                            output_queue.put(f"\n\n{message}\n\n")
                        continue
                    display_name = TOOL_DISPLAY_NAMES.get(
                        tool_name,
                        tool_name.replace("_", " ").title(),
                    )
                    output_queue.put(f"\n\n> Running **{display_name}**\n")
                    continue

                if event.name == "tool_output":
                    final_text_since_tool = False
                    call_id = _extract_call_id(raw)
                    tool_name = call_id_to_name.get(call_id or "", "tool")
                    if tool_name == PROGRESS_TOOL_NAME:
                        continue
                    display_name = TOOL_DISPLAY_NAMES.get(
                        tool_name,
                        tool_name.replace("_", " ").title(),
                    )
                    output_queue.put(f"\n> Done **{display_name}**\n\n")

            if pending_assistant_message:
                output_queue.put(f"\n\n{pending_assistant_message}\n\n")
                final_text_since_tool = True
            if not final_text_since_tool:
                final_output = getattr(result, "final_output", None)
                if isinstance(final_output, str) and final_output.strip():
                    output_queue.put(f"\n\n{final_output.strip()}\n")
                else:
                    output_queue.put(f"\n\n{EMPTY_RESPONSE}\n")
        except Exception as exc:
            output_queue.put(f"\n\n{_stream_error_message(exc)}\n")
        finally:
            output_queue.put(sentinel)

    asyncio.run_coroutine_threadsafe(produce(), loop)

    def stream_generator() -> Iterator[str]:
        while True:
            item = output_queue.get()
            if item is sentinel:
                break
            yield str(item)

    return stream_generator()
