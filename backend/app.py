from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict
import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator

from process_command.processor import process_text_command

# Load environment variables from .env file (if it exists)
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    load_dotenv(env_file)

logger = logging.getLogger(__name__)


class CommandRequest(BaseModel):
    """Incoming command payload from the frontend."""

    model_config = ConfigDict(extra="forbid")

    command: str = Field(..., min_length=1, max_length=500)
    @field_validator("command")
    @classmethod
    def normalize_command(cls, value: str) -> str:
        """Trim command text and reject blank input."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("command must not be empty")
        return normalized_value


class CommandResponse(BaseModel):
    """Structured assistant response returned to the frontend."""

    model_config = ConfigDict(extra="forbid")

    action: str
    message: str
    url: str | None = None


class RootResponse(BaseModel):
    """Response shape for the API root endpoint."""

    service: str
    version: str
    endpoints: Dict[str, str]



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup code using FastAPI lifespan handlers (recommended)."""

    _configure_logging()
    logger.info("Sofia backend started")
    yield


app = FastAPI(title="SOFIA Assistant Backend", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_model=RootResponse)
def root() -> RootResponse:
    """API documentation and available endpoints."""

    # The error happened because `dict[str, str]` forced every value to be a string,
    # but `endpoints` is actually a dictionary.
    # This model fixes validation by explicitly allowing `endpoints: Dict[str, str]`.
    return RootResponse(
        service="Sofia AI Assistant",
        version="1.0.0",
        endpoints={
            "command": "POST /api/command",
            "health": "GET /health",
            "docs": "GET /docs",
        },
    )


@app.get("/health")
def health() -> dict[str, str]:
    """Simple health check for load balancers."""
    return {"status": "ok"}

@app.get("/config")
def config() -> dict[str, str]:
    """Return env configuration."""
    return dict(os.environ) 

@app.post("/api/command", response_model=CommandResponse)
async def command_api(payload: CommandRequest, request: Request) -> CommandResponse:
    """Handle command requests with simple logging and AI fallback."""

    command = payload.command.strip()
    client_host = request.client.host if request.client else "unknown"

    logger.info(
        "request path=%s client=%s command=%s",
        request.url.path,
        client_host,
        command,
    )

    result = await process_text_command(command)

    logger.info(
        "response path=%s client=%s action=%s",
        request.url.path,
        client_host,
        result.get("action"),
    )
    return CommandResponse(
        action=result.get("action", "chat"),
        message=result.get("message", ""),
        url=result.get("url"),
    )


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
