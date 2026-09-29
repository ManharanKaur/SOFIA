"""
app.py
------
SOFIA backend — FastAPI application.

New endpoints (vs original)
---------------------------
GET  /ws/agent              — Desktop Agent WebSocket connection (authenticated)
GET  /api/agent/status      — Returns whether the Desktop Agent is connected
POST /api/permission/respond — Frontend sends the user's permission decision
GET  /config                — Returns env config (Gemini key removed)

Unchanged endpoints
-------------------
GET  /                      — API docs root
GET  /health                — Health check
POST /api/command           — Main command endpoint
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Literal
import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pathlib import Path
from dotenv import load_dotenv

env_file = Path(__file__).parent / ".env"
if env_file.exists():
    load_dotenv(env_file)

from support_functions.helpers import _read_env_key
from support_functions.agent_bridge import bridge
from process_command.processor import process_text_command

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class CommandRequest(BaseModel):
    """Incoming command payload from the frontend."""

    model_config = ConfigDict(extra="forbid")

    command: str = Field(..., min_length=1, max_length=500)
    history: list["ChatTurn"] = Field(default_factory=list, max_length=20)

    @field_validator("command")
    @classmethod
    def normalize_command(cls, value: str) -> str:
        """Trim command text and reject blank input."""
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("command must not be empty")
        return normalized_value


class ChatTurn(BaseModel):
    """Single conversation turn used to provide chat memory."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=4000)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        """Trim turn text and reject blank input."""
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("content must not be empty")
        return normalized_value


CommandRequest.model_rebuild()


class CommandResponse(BaseModel):
    """Structured assistant response returned to the frontend."""

    model_config = ConfigDict(extra="forbid")

    action: str
    message: str
    url: str | None = None
    agent_connected: bool = False


class RootResponse(BaseModel):
    """Response shape for the API root endpoint."""

    service: str
    version: str
    endpoints: Dict[str, str]


class PermissionResponseRequest(BaseModel):
    """Payload from the frontend confirming or denying a permission request."""

    model_config = ConfigDict(extra="forbid")

    command_id: str = Field(..., min_length=1, max_length=128)
    permission: str = Field(..., min_length=1, max_length=64)
    granted: bool
    remember: bool = False


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup code using FastAPI lifespan handlers."""
    _configure_logging()
    logger.info("Sofia backend started")
    yield


app = FastAPI(title="SOFIA Assistant Backend", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Standard HTTP endpoints
# ---------------------------------------------------------------------------

@app.get("/", response_model=RootResponse)
def root() -> RootResponse:
    """API documentation and available endpoints."""
    return RootResponse(
        service="Sofia AI Assistant",
        version="2.0.0",
        endpoints={
            "command":            "POST /api/command",
            "agent_status":       "GET /api/agent/status",
            "permission_respond": "POST /api/permission/respond",
            "agent_ws":           "GET /ws/agent?token=<SOFIA_AGENT_TOKEN>",
            "health":             "GET /health",
            "docs":               "GET /docs",
        },
    )


@app.get("/health")
def health() -> dict[str, str]:
    """Simple health check for load balancers."""
    return {"status": "ok"}


@app.get("/api/agent/status")
def agent_status() -> dict[str, bool]:
    """
    Return whether the SOFIA Desktop Agent is currently connected.
    The frontend polls this to show the connection indicator.
    """
    return {"connected": bridge.is_agent_connected}


@app.post("/api/command", response_model=CommandResponse)
async def command_api(payload: CommandRequest, request: Request) -> CommandResponse:
    """Handle command requests — routes to Desktop Agent or Ollama fallback."""
    command = payload.command.strip()
    client_host = request.client.host if request.client else "unknown"

    logger.info(
        "request path=%s client=%s command=%s",
        request.url.path,
        client_host,
        command,
    )

    result = await process_text_command(
        command,
        history=[turn.model_dump() for turn in payload.history],
    )

    logger.info(
        "response path=%s client=%s action=%s agent_connected=%s",
        request.url.path,
        client_host,
        result.get("action"),
        result.get("agent_connected", False),
    )

    return CommandResponse(
        action=result.get("action", "chat"),
        message=result.get("message", ""),
        url=result.get("url"),
        agent_connected=result.get("agent_connected", bridge.is_agent_connected),
    )


@app.post("/api/permission/respond")
async def permission_respond(payload: PermissionResponseRequest) -> dict[str, str]:
    """
    Accept the user's permission decision from the frontend and forward it
    to the Desktop Agent.
    """
    await bridge.forward_permission_response(
        command_id=payload.command_id,
        permission=payload.permission,
        granted=payload.granted,
        remember=payload.remember,
    )
    status = "granted" if payload.granted else "denied"
    logger.info(
        "Permission %s for command_id=%s permission=%s",
        status,
        payload.command_id,
        payload.permission,
    )
    return {"status": status}


# ---------------------------------------------------------------------------
# WebSocket: Desktop Agent connection
# ---------------------------------------------------------------------------

@app.websocket("/ws/agent")
async def agent_websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(default=""),
) -> None:
    """
    Authenticated WebSocket endpoint for the SOFIA Desktop Agent.

    The agent connects here, sends a ``register`` message with its token,
    and then receives ``command`` messages to process.  It replies with
    ``result`` and ``permission_request`` messages.

    Authentication: ?token=<SOFIA_AGENT_TOKEN>
    """
    await websocket.accept()
    logger.info("Agent WebSocket connection attempt from %s", websocket.client)

    try:
        await bridge.accept_agent(websocket, token)
    except PermissionError as exc:
        await websocket.send_text(
            f'{{"type":"error","message":"{exc}"}}'
        )
        await websocket.close(code=4001)
        logger.warning("Agent connection rejected: invalid token.")
        return
    except RuntimeError as exc:
        await websocket.send_text(
            f'{{"type":"error","message":"{exc}"}}'
        )
        await websocket.close(code=4002)
        return

    try:
        await bridge.run_agent_message_loop(websocket)
    except WebSocketDisconnect:
        logger.info("Agent WebSocket disconnected normally.")


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def _configure_logging() -> None:
    """Configure application logging only when root handlers are not already present."""
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


if __name__ == "__main__":
    import uvicorn

    _configure_logging()
    uvicorn.run(app, host="0.0.0.0", port=8000)
