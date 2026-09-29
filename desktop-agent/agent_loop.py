"""
agent_loop.py
-------------
The core multi-step agent loop for the SOFIA Desktop Agent.

Loop lifecycle (per command)
----------------------------
1. Receive user message.
2. Call Ollama → get text reply OR list of tool calls.
3. For each tool call:
   a. Look up the tool's permission group.
   b. If permission NOT granted → emit ``permission_request`` event and
      suspend until the frontend user grants/denies.
   c. If denied → skip this tool, record denial in result.
   d. If granted → call tool_executor.execute_tool().
   e. Feed the tool result back to Ollama as a tool-role message.
4. After all tool calls are resolved, get the final text reply from Ollama.
5. Return the assembled result.

The loop supports multiple sequential tool calls in a single turn.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Awaitable

from ollama_client import ask_ollama, OllamaToolCall
from tool_executor import execute_tool
from tool_registry import get_tool
from permission_groups import get_group_for_tool, is_sensitive
from permission_store import is_granted, save_decision

logger = logging.getLogger(__name__)

# Type alias: the callback the agent uses to send permission requests to
# the frontend and await the user's decision.
PermissionCallback = Callable[
    [str, str, str],       # (group_key, label, description)
    Awaitable[tuple[bool, bool]],  # returns (granted, remember)
]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run_agent_loop(
    user_message: str,
    history: list[dict[str, Any]] | None,
    request_permission: PermissionCallback,
) -> dict[str, Any]:
    """
    Run a full agent turn and return the structured result.

    Parameters
    ----------
    user_message:
        Raw text from STT or the chat input.
    history:
        Prior conversation turns for context.
    request_permission:
        Async callback that pauses the loop, shows the user a permission
        dialog, and returns ``(granted, remember)``.

    Returns
    -------
    dict with keys:
        action   (str)   — "chat" | "tool_result" | "error"
        message  (str)   — final human-readable text
        results  (list)  — list of per-tool execution results
        denied   (list)  — list of tool names that were denied
    """
    logger.info("Agent loop started for message: %r", user_message)

    # Phase 1: initial LLM call.
    ollama_resp = await ask_ollama(user_message, history)

    if not ollama_resp.has_tool_calls:
        # Pure conversational reply — no tools needed.
        return {
            "action": "chat",
            "message": ollama_resp.text or "I'm not sure how to respond to that.",
            "results": [],
            "denied": [],
        }

    # Phase 2: resolve permissions and execute tools.
    tool_results: list[dict[str, Any]] = []
    denied_tools: list[str] = []
    conversation_messages: list[dict[str, Any]] = []

    for tool_call in ollama_resp.tool_calls:
        result = await _handle_tool_call(
            tool_call, request_permission, tool_results, denied_tools
        )
        if result is not None:
            # Append tool result as a "tool" message for Ollama context.
            conversation_messages.append(
                {
                    "role": "tool",
                    "content": result.get("message", ""),
                    "name": tool_call.tool_name,
                }
            )

    # Phase 3: get final natural-language summary from Ollama.
    if conversation_messages:
        full_history = (history or []) + conversation_messages
        summary_resp = await ask_ollama(
            "Summarise what you just did for the user in one friendly sentence.",
            full_history,
        )
        final_message = summary_resp.text or _compose_fallback_message(
            tool_results, denied_tools
        )
    else:
        final_message = _compose_fallback_message(tool_results, denied_tools)

    return {
        "action": "tool_result",
        "message": final_message,
        "results": tool_results,
        "denied": denied_tools,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _handle_tool_call(
    tool_call: OllamaToolCall,
    request_permission: PermissionCallback,
    tool_results: list[dict[str, Any]],
    denied_tools: list[str],
) -> dict[str, Any] | None:
    """
    Validate, permission-check, and execute a single tool call.

    Returns the execution result dict, or None if the tool was denied/unknown.
    """
    tool_def = get_tool(tool_call.tool_name)
    if tool_def is None:
        logger.warning("LLM requested unknown tool: %r", tool_call.tool_name)
        return None

    group = get_group_for_tool(tool_call.tool_name)
    if group is None:
        logger.error("Tool '%s' has no permission group configured.", tool_call.tool_name)
        return None

    # Check whether permission has already been granted (and tool is not sensitive).
    needs_confirmation = is_sensitive(tool_call.tool_name) or not is_granted(group.key)

    if needs_confirmation:
        logger.info(
            "Requesting permission '%s' for tool '%s'.",
            group.key,
            tool_call.tool_name,
        )
        try:
            granted, remember = await asyncio.wait_for(
                request_permission(group.key, group.label, group.description),
                timeout=60,  # user has 60 s to respond
            )
        except asyncio.TimeoutError:
            logger.warning("Permission request timed out for group '%s'.", group.key)
            denied_tools.append(tool_call.tool_name)
            return None

        save_decision(group.key, granted=granted, remember=remember)

        if not granted:
            logger.info("User denied permission '%s'.", group.key)
            denied_tools.append(tool_call.tool_name)
            return None

    # Execute the tool.
    result = execute_tool(tool_call.tool_name, tool_call.arguments)
    tool_results.append(
        {
            "tool": tool_call.tool_name,
            "arguments": tool_call.arguments,
            **result,
        }
    )

    if not result["success"]:
        logger.warning("Tool '%s' failed: %s", tool_call.tool_name, result["message"])

    return result


def _compose_fallback_message(
    results: list[dict[str, Any]],
    denied: list[str],
) -> str:
    """Build a plain-English summary when Ollama cannot produce one."""
    parts: list[str] = []

    for r in results:
        parts.append(r.get("message", "Done."))

    if denied:
        denied_str = ", ".join(denied)
        parts.append(
            f"I was not able to run {denied_str} because permission was denied."
        )

    return " ".join(parts) if parts else "Done."
