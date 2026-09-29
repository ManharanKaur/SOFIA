"""
agent_main.py
-------------
Entry point for the SOFIA Desktop Agent.

Run with:
    python agent_main.py

The agent:
1. Configures logging.
2. Validates that Ollama is reachable (exits with a clear message if not).
3. Starts the WebSocket client loop (reconnects automatically).
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

import httpx
from dotenv import load_dotenv

# Load environment variables from desktop-agent/.env
load_dotenv()


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


# ---------------------------------------------------------------------------
# Ollama health check
# ---------------------------------------------------------------------------

async def _check_ollama() -> bool:
    """Return True when the local Ollama server responds on /api/tags."""
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{base}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    _configure_logging()
    logger = logging.getLogger("sofia.agent")

    logger.info("=" * 60)
    logger.info("  SOFIA Desktop Agent starting up…")
    logger.info("=" * 60)

    # Verify Ollama is running before attempting to connect.
    if not await _check_ollama():
        ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
        logger.error(
            "\n"
            "  ✗ Cannot reach Ollama at http://localhost:11434\n\n"
            "  To fix this:\n"
            "    1. Install Ollama: https://ollama.com/download\n"
            "    2. Start it:  ollama serve\n"
            f"    3. Pull model: ollama pull {ollama_model}\n"
        )
        sys.exit(1)

    logger.info("✓ Ollama is running.")

    # Import here so Ollama check happens first.
    from ws_client import run_ws_client

    agent_token = os.getenv("AGENT_TOKEN", "")
    if not agent_token:
        logger.error(
            "\n"
            "  ✗ AGENT_TOKEN is not set.\n\n"
            "  To fix this:\n"
            "    1. Generate a token:  python -c \"import secrets; print(secrets.token_hex(32))\"\n"
            "    2. Add AGENT_TOKEN=<token> to desktop-agent/.env\n"
            "    3. Add SOFIA_AGENT_TOKEN=<same token> to your Render environment vars\n"
        )
        sys.exit(1)

    logger.info("✓ Agent token configured.")
    logger.info("Connecting to Render backend…")

    await run_ws_client()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSOFIA Desktop Agent stopped.")
