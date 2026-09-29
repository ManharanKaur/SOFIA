"""
ws_client.py
------------
Authenticated WebSocket client that connects the Desktop Agent to the
Render backend.

Protocol (JSON messages over WebSocket)
----------------------------------------
Agent → Backend  (REGISTER)
{
    "type":       "register",
    "agent_token": "<AGENT_TOKEN>",
    "session_id": "<uuid4>"
}

Backend → Agent  (COMMAND)
{
    "type":        "command",
    "command_id":  "<uuid4>",
    "command":     "Open Chrome and play study music",
    "history":     [...]
}

Agent → Backend  (PERMISSION_REQUEST)
{
    "type":         "permission_request",
    "command_id":   "<uuid4>",
    "permission":   "browser_control",
    "label":        "Browser Control",
    "description":  "Allow SOFIA to open Chrome, Safari, or Firefox …"
}

Backend/Frontend → Agent  (PERMISSION_RESPONSE)
{
    "type":         "permission_response",
    "command_id":   "<uuid4>",
    "permission":   "browser_control",
    "granted":      true,
    "remember":     true
}

Agent → Backend  (RESULT)
{
    "type":       "result",
    "command_id": "<uuid4>",
    "action":     "tool_result",
    "message":    "Opened Chrome and started playing study music.",
    "results":    [...],
    "denied":     []
}

Agent → Backend  (HEARTBEAT)
{
    "type": "heartbeat"
}

Backend → Agent  (HEARTBEAT_ACK)
{
    "type": "heartbeat_ack"
}
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import ssl
import uuid
from typing import Any

import websockets
from websockets.asyncio.client import connect as ws_connect
from dotenv import load_dotenv

try:
    import certifi
except ImportError:
    certifi = None

from agent_loop import run_agent_loop

load_dotenv()

logger = logging.getLogger(__name__)

_BACKEND_WS_URL = os.getenv(
    "RENDER_BACKEND_WS_URL",
    "wss://sofia-backend-csow.onrender.com/ws/agent",
)
_AGENT_TOKEN = os.getenv("AGENT_TOKEN", "")
_HEARTBEAT_INTERVAL = 25  # seconds
_RECONNECT_DELAY_SECONDS = 5


# ---------------------------------------------------------------------------
# Pending permission requests
# (command_id + permission_key) -> asyncio.Future[tuple[bool, bool]]
# ---------------------------------------------------------------------------
_pending_permissions: dict[str, asyncio.Future[tuple[bool, bool]]] = {}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run_ws_client() -> None:
    """
    Connect to the Render backend, authenticate, and enter the message loop.
    Reconnects automatically on disconnect.
    """
    if not _AGENT_TOKEN:
        logger.error(
            "AGENT_TOKEN is not set. "
            "Add it to desktop-agent/.env and also set SOFIA_AGENT_TOKEN on Render."
        )
        return

    session_id = str(uuid.uuid4())
    logger.info("Starting SOFIA Desktop Agent (session=%s)", session_id)

    while True:
        try:
            await _connect_and_loop(session_id)
        except (
            websockets.exceptions.ConnectionClosedError,
            websockets.exceptions.ConnectionClosedOK,
            OSError,
        ) as exc:
            logger.warning(
                "WebSocket disconnected: %s. Reconnecting in %ss…",
                exc,
                _RECONNECT_DELAY_SECONDS,
            )
        except Exception:
            logger.exception("Unexpected error in WebSocket loop. Reconnecting…")

        await asyncio.sleep(_RECONNECT_DELAY_SECONDS)


# ---------------------------------------------------------------------------
# Connection lifecycle
# ---------------------------------------------------------------------------

async def _connect_and_loop(session_id: str) -> None:
    """Open a WebSocket connection and handle messages until it closes."""
    logger.info("Connecting to %s", _BACKEND_WS_URL)

    connect_kwargs: dict[str, Any] = {}
    if _BACKEND_WS_URL.startswith("wss://"):
        if certifi:
            ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        else:
            ssl_ctx = ssl.create_default_context()
        connect_kwargs["ssl"] = ssl_ctx

    async with ws_connect(_BACKEND_WS_URL, **connect_kwargs) as websocket:
        # Register with the backend.
        await _send(websocket, {
            "type": "register",
            "agent_token": _AGENT_TOKEN,
            "session_id": session_id,
        })
        logger.info("Registered with backend (session=%s)", session_id)

        # Run heartbeat and message handler concurrently.
        await asyncio.gather(
            _heartbeat_loop(websocket),
            _message_loop(websocket, session_id),
        )


async def _heartbeat_loop(websocket: Any) -> None:
    """Send a periodic heartbeat so Render does not close the idle connection."""
    while True:
        await asyncio.sleep(_HEARTBEAT_INTERVAL)
        try:
            await _send(websocket, {"type": "heartbeat"})
        except Exception:
            break


async def _message_loop(websocket: Any, session_id: str) -> None:
    """Receive and dispatch messages from the backend."""
    async for raw_message in websocket:
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError:
            logger.warning("Received non-JSON message; ignoring.")
            continue

        message_type = message.get("type", "")

        if message_type == "command":
            asyncio.create_task(
                _handle_command(websocket, message, session_id)
            )

        elif message_type == "permission_response":
            _resolve_permission(message)

        elif message_type == "heartbeat_ack":
            logger.debug("Heartbeat acknowledged.")

        elif message_type == "error":
            logger.error("Backend error: %s", message.get("message"))

        else:
            logger.debug("Unknown message type: %s", message_type)


# ---------------------------------------------------------------------------
# Command handler
# ---------------------------------------------------------------------------

async def _handle_command(
    websocket: Any,
    message: dict[str, Any],
    session_id: str,
) -> None:
    """Process a command from the backend, running the full agent loop."""
    command_id = str(message.get("command_id", uuid.uuid4()))
    user_message = str(message.get("command", "")).strip()
    history = message.get("history", [])

    logger.info("Command received [%s]: %r", command_id, user_message)

    async def request_permission(
        group_key: str,
        label: str,
        description: str,
    ) -> tuple[bool, bool]:
        """Send a permission_request to the frontend and await the response."""
        future: asyncio.Future[tuple[bool, bool]] = asyncio.get_event_loop().create_future()
        pending_key = f"{command_id}:{group_key}"
        _pending_permissions[pending_key] = future

        try:
            await _send(websocket, {
                "type": "permission_request",
                "command_id": command_id,
                "permission": group_key,
                "label": label,
                "description": description,
            })
            return await future
        finally:
            _pending_permissions.pop(pending_key, None)

    try:
        result = await run_agent_loop(user_message, history, request_permission)
    except Exception as exc:
        logger.exception("Agent loop failed for command [%s]", command_id)
        result = {
            "action": "error",
            "message": f"An internal error occurred: {exc}",
            "results": [],
            "denied": [],
        }

    await _send(websocket, {
        "type": "result",
        "command_id": command_id,
        "session_id": session_id,
        **result,
    })


# ---------------------------------------------------------------------------
# Permission resolution
# ---------------------------------------------------------------------------

def _resolve_permission(message: dict[str, Any]) -> None:
    """
    Resolve a pending permission future when the frontend responds.
    """
    command_id = str(message.get("command_id", ""))
    group_key = str(message.get("permission", ""))
    granted = bool(message.get("granted", False))
    remember = bool(message.get("remember", False))

    pending_key = f"{command_id}:{group_key}"
    future = _pending_permissions.get(pending_key)

    if future and not future.done():
        future.set_result((granted, remember))
    else:
        logger.warning(
            "Received permission_response for unknown pending key: %s",
            pending_key,
        )


# ---------------------------------------------------------------------------
# Send helper
# ---------------------------------------------------------------------------

async def _send(websocket: Any, payload: dict[str, Any]) -> None:
    """Serialize and send a JSON message."""
    await websocket.send(json.dumps(payload))
    logger.debug("Sent message type=%s", payload.get("type"))
