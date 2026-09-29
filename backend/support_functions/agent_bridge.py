"""
agent_bridge.py
---------------
Manages the live WebSocket connection between the Render backend and the
SOFIA Desktop Agent running on the user's computer.

Responsibilities
----------------
- Accept a single authenticated agent connection at a time.
- Route incoming ``/api/command`` requests to the agent.
- Forward ``permission_request`` messages from the agent to waiting command
  futures, so the frontend can display them.
- Forward ``permission_response`` messages from the frontend back to the agent.
- Detect when the agent disconnects and clear state.

Thread / async safety
---------------------
This module uses asyncio primitives only.  FastAPI runs every endpoint in
the same event loop, so shared state is safe without locks.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

_SOFIA_AGENT_TOKEN = os.getenv("SOFIA_AGENT_TOKEN", "")


# ---------------------------------------------------------------------------
# Shared mutable state (one event loop → no locking needed)
# ---------------------------------------------------------------------------

class AgentBridge:
    """Singleton that holds the live agent connection and pending command futures."""

    def __init__(self) -> None:
        self._agent_ws: WebSocket | None = None
        self._agent_session_id: str | None = None

        # command_id -> Future[dict]  (result from the agent)
        self._pending_commands: dict[str, asyncio.Future[dict[str, Any]]] = {}

        # (command_id, permission_key) -> Future[tuple[bool,bool]]
        # These are resolved when the frontend POSTs a permission response.
        self._pending_permissions: dict[str, asyncio.Future[tuple[bool, bool]]] = {}

    # ------------------------------------------------------------------
    # Agent connection lifecycle
    # ------------------------------------------------------------------

    @property
    def is_agent_connected(self) -> bool:
        return self._agent_ws is not None

    async def accept_agent(self, websocket: WebSocket, token: str) -> None:
        """
        Accept and authenticate a new agent WebSocket connection.
        Raises ``PermissionError`` when the token is wrong.
        """
        expected_token = os.getenv("SOFIA_AGENT_TOKEN", "").strip()
        if not expected_token:
            raise RuntimeError(
                "SOFIA_AGENT_TOKEN is not configured on the backend. "
                "Set it in your Render environment variables or backend/.env."
            )

        received_token = token.strip()
        # If token was not provided as a query param, read the first message (registration)
        if not received_token:
            try:
                raw_register = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
                msg = json.loads(raw_register)
                if msg.get("type") == "register":
                    received_token = str(msg.get("agent_token", "")).strip()
                    self._agent_session_id = msg.get("session_id")
            except Exception as exc:
                logger.warning("Failed to receive registration message: %s", exc)
                raise PermissionError("Registration handshake failed.")

        if received_token != expected_token:
            logger.warning("Agent connection rejected: invalid token.")
            raise PermissionError("Invalid agent token.")

        self._agent_ws = websocket
        logger.info("Desktop Agent connected and authenticated (session=%s).", self._agent_session_id)

    def _disconnect_agent(self) -> None:
        """Mark the agent as disconnected and fail all pending futures."""
        self._agent_ws = None
        self._agent_session_id = None
        logger.warning("Desktop Agent disconnected.")

        for future in self._pending_commands.values():
            if not future.done():
                future.set_exception(RuntimeError("Agent disconnected."))
        self._pending_commands.clear()

        for future in self._pending_permissions.values():
            if not future.done():
                future.set_result((False, False))
        self._pending_permissions.clear()

    # ------------------------------------------------------------------
    # Agent message loop (runs for the lifetime of the agent connection)
    # ------------------------------------------------------------------

    async def run_agent_message_loop(self, websocket: WebSocket) -> None:
        """
        Read messages from the agent WebSocket until it disconnects.
        Called from the /ws/agent endpoint handler.
        """
        try:
            async for raw in websocket.iter_text():
                await self._dispatch_agent_message(raw)
        except WebSocketDisconnect:
            pass
        finally:
            self._disconnect_agent()

    async def _dispatch_agent_message(self, raw: str) -> None:
        """Parse and route a single agent message."""
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Non-JSON message from agent; ignoring.")
            return

        msg_type = message.get("type", "")

        if msg_type == "register":
            self._agent_session_id = message.get("session_id")
            logger.info("Agent registered session_id=%s", self._agent_session_id)

        elif msg_type == "result":
            command_id = str(message.get("command_id", ""))
            future = self._pending_commands.pop(command_id, None)
            if future and not future.done():
                future.set_result(message)
            else:
                logger.warning("Received result for unknown command_id: %s", command_id)

        elif msg_type == "permission_request":
            # Forward to the frontend via the pending_permission future.
            # The frontend will call POST /api/permission_response.
            command_id = str(message.get("command_id", ""))
            permission = str(message.get("permission", ""))
            pending_key = f"{command_id}:{permission}"
            # Store the raw permission_request so the frontend command future
            # can surface it. We re-use _pending_permissions to hold the
            # forwarded Future that the frontend will resolve.
            future: asyncio.Future[tuple[bool, bool]] = (
                asyncio.get_event_loop().create_future()
            )
            self._pending_permissions[pending_key] = future
            logger.info(
                "Permission request forwarded: command=%s permission=%s",
                command_id,
                permission,
            )
            # Signal the command future so the frontend knows to show the dialog.
            cmd_future = self._pending_commands.get(command_id)
            if cmd_future and not cmd_future.done():
                # Don't resolve the command future yet — just signal the
                # permission request as an interim event by broadcasting it.
                # We store the message in a special "interim" slot.
                self._pending_commands[f"perm:{pending_key}"] = future  # type: ignore[assignment]

        elif msg_type == "heartbeat":
            # Acknowledge heartbeat.
            if self._agent_ws:
                await self._send_to_agent({"type": "heartbeat_ack"})

        else:
            logger.debug("Unhandled agent message type: %s", msg_type)

    # ------------------------------------------------------------------
    # Frontend → Agent command dispatch
    # ------------------------------------------------------------------

    async def send_command_to_agent(
        self,
        command: str,
        history: list[dict[str, Any]],
        timeout: float = 90,
    ) -> dict[str, Any]:
        """
        Forward a user command to the Desktop Agent and wait for the result.

        Raises
        ------
        RuntimeError  — if no agent is connected.
        asyncio.TimeoutError — if the agent takes longer than *timeout* seconds.
        """
        if not self._agent_ws:
            raise RuntimeError("Desktop Agent is not connected.")

        command_id = str(uuid.uuid4())
        future: asyncio.Future[dict[str, Any]] = (
            asyncio.get_event_loop().create_future()
        )
        self._pending_commands[command_id] = future

        await self._send_to_agent({
            "type": "command",
            "command_id": command_id,
            "command": command,
            "history": history,
        })

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending_commands.pop(command_id, None)
            raise

    # ------------------------------------------------------------------
    # Frontend → Agent permission response
    # ------------------------------------------------------------------

    async def forward_permission_response(
        self,
        command_id: str,
        permission: str,
        granted: bool,
        remember: bool,
    ) -> None:
        """
        Forward the user's permission decision to the Desktop Agent.
        Also resolves the local pending_permission future.
        """
        pending_key = f"{command_id}:{permission}"
        future = self._pending_permissions.pop(pending_key, None)
        if future and not future.done():
            future.set_result((granted, remember))

        if self._agent_ws:
            await self._send_to_agent({
                "type": "permission_response",
                "command_id": command_id,
                "permission": permission,
                "granted": granted,
                "remember": remember,
            })

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _send_to_agent(self, payload: dict[str, Any]) -> None:
        """Serialize and send a message to the connected agent."""
        if self._agent_ws:
            try:
                await self._agent_ws.send_text(json.dumps(payload))
            except Exception as exc:
                logger.error("Failed to send message to agent: %s", exc)

    def get_pending_permission_requests(self) -> list[dict[str, Any]]:
        """
        Return a list of currently pending permission requests.
        Used by the frontend polling endpoint.
        """
        # Reconstruct from pending_permissions keys.
        results = []
        for key in list(self._pending_permissions.keys()):
            if key.startswith("perm:"):
                _, cmd_perm = key.split("perm:", 1)
                command_id, permission = cmd_perm.rsplit(":", 1)
                results.append({
                    "command_id": command_id,
                    "permission": permission,
                })
        return results


# Module-level singleton — imported by app.py.
bridge = AgentBridge()
