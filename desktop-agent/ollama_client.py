"""
ollama_client.py
----------------
Thin async client for the local Ollama inference server.

Responsibilities
----------------
- Format the request payload (messages + tool schemas).
- Send the request to http://localhost:11434/api/chat.
- Parse the response and return either a text reply or a list of tool calls.
- Never expose raw model output to the executor without parsing.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

from tool_registry import OLLAMA_TOOL_SCHEMAS

logger = logging.getLogger(__name__)

_OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
_REQUEST_TIMEOUT = 120  # seconds


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

class OllamaToolCall:
    """Represents a single tool call returned by the LLM."""

    __slots__ = ("tool_name", "arguments")

    def __init__(self, tool_name: str, arguments: dict[str, Any]) -> None:
        self.tool_name = tool_name
        self.arguments = arguments

    def __repr__(self) -> str:  # pragma: no cover
        return f"OllamaToolCall(tool_name={self.tool_name!r}, arguments={self.arguments!r})"


class OllamaResponse:
    """Parsed response from Ollama — either a text reply or tool calls."""

    __slots__ = ("text", "tool_calls")

    def __init__(
        self,
        text: str | None = None,
        tool_calls: list[OllamaToolCall] | None = None,
    ) -> None:
        self.text = text
        self.tool_calls = tool_calls or []

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are SOFIA, a helpful local AI voice assistant running on the user's Mac.\n"
    "When the user asks you to perform an action on their computer — such as opening\n"
    "an app, playing music, searching the web, or adjusting volume — call the\n"
    "appropriate tool instead of describing what you would do.\n"
    "For conversational questions (greetings, knowledge questions, news) respond\n"
    "with plain text. Keep replies concise and natural.\n"
    "Never invent tool names. Only use the tools provided to you."
)


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------

async def ask_ollama(
    user_message: str,
    history: list[dict[str, Any]] | None = None,
) -> OllamaResponse:
    """
    Send *user_message* to the local Ollama model and return a parsed response.

    Parameters
    ----------
    user_message:
        The current user input (voice transcript or text).
    history:
        List of prior turns in ``{"role": "...", "content": "..."}`` format.
        Passed as conversation context to the model.

    Returns
    -------
    OllamaResponse with either ``.text`` (conversational reply)
    or ``.tool_calls`` (list of OllamaToolCall).
    """
    messages = _build_messages(user_message, history)
    payload = {
        "model": _OLLAMA_MODEL,
        "messages": messages,
        "tools": OLLAMA_TOOL_SCHEMAS,
        "stream": False,
    }

    logger.debug(
        "Sending request to Ollama model=%s messages=%d",
        _OLLAMA_MODEL,
        len(messages),
    )

    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            response = await client.post(
                f"{_OLLAMA_BASE}/api/chat",
                json=payload,
            )
            response.raise_for_status()
    except httpx.ConnectError:
        logger.error("Cannot connect to Ollama at %s", _OLLAMA_BASE)
        return OllamaResponse(
            text=(
                "I cannot connect to the local AI model. "
                "Please make sure Ollama is running (`ollama serve`) "
                f"and the model is loaded (`ollama pull {_OLLAMA_MODEL}`)."
            )
        )
    except httpx.TimeoutException:
        logger.error("Ollama request timed out after %s seconds", _REQUEST_TIMEOUT)
        return OllamaResponse(text="The local AI model took too long to respond. Please try again.")
    except httpx.HTTPStatusError as exc:
        logger.error("Ollama returned HTTP %s", exc.response.status_code)
        return OllamaResponse(text=f"Local AI model error: HTTP {exc.response.status_code}.")

    return _parse_ollama_response(response.json())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_messages(
    user_message: str,
    history: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Assemble the messages array (system + history + current turn)."""
    messages: list[dict[str, Any]] = [{"role": "system", "content": _SYSTEM_PROMPT}]

    for turn in (history or [])[-10:]:
        role = str(turn.get("role", "user")).strip().lower()
        content = str(turn.get("content", "")).strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": user_message.strip()})
    return messages


def _parse_ollama_response(raw: dict[str, Any]) -> OllamaResponse:
    """
    Parse the raw JSON body from ``/api/chat``.

    Ollama tool-call format:
    {
      "message": {
        "role": "assistant",
        "content": "",
        "tool_calls": [
          {
            "function": {
              "name": "open_browser",
              "arguments": {"browser": "Chrome"}
            }
          }
        ]
      }
    }
    """
    message = raw.get("message", {})
    raw_tool_calls = message.get("tool_calls")

    if raw_tool_calls:
        tool_calls: list[OllamaToolCall] = []
        for tc in raw_tool_calls:
            fn = tc.get("function", {})
            name = str(fn.get("name", "")).strip()
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            if name:
                tool_calls.append(OllamaToolCall(tool_name=name, arguments=args))
        return OllamaResponse(tool_calls=tool_calls)

    text = str(message.get("content", "")).strip()
    return OllamaResponse(text=text or "I didn't understand that. Could you rephrase?")
