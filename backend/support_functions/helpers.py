"""
helpers.py
----------
Shared utility functions for the SOFIA backend.

Changes from original
---------------------
- Removed: Google Gemini ``ask_ai()`` function and all genai imports.
- Added:   ``ask_ollama()`` — calls the local Ollama server via HTTP.
- Kept:    ``get_page_map()``, ``open_url_in_browser()``, ``get_news()``,
           ``_read_env_key()``, and URL safety helpers unchanged.
"""

from __future__ import annotations

import logging
import os
import webbrowser
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests as _requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Environment helper
# ---------------------------------------------------------------------------

def _read_env_key(*names: str) -> str:
    """Read the first non-empty env value from candidate names."""
    for name in names:
        value = (os.getenv(name) or "").strip().strip('"').strip("'")
        if value:
            return value
    return ""


# ---------------------------------------------------------------------------
# Page map (unchanged from original)
# ---------------------------------------------------------------------------

def _default_page_map() -> dict[str, str]:
    """Return built-in pages used when no external library is available."""
    return {
        "google": "https://www.google.com",
        "youtube": "https://www.youtube.com",
        "you tube": "https://www.youtube.com",
        "spotify": "https://open.spotify.com",
        "github": "https://github.com",
        "gmail": "https://mail.google.com",
    }


def _safe_url(url: str) -> str | None:
    """Return a sanitized HTTP or HTTPS URL, or ``None`` when it is unsafe."""
    parsed_url = urlsplit(url.strip())
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        return None
    return urlunsplit(
        (
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path,
            parsed_url.query,
            parsed_url.fragment,
        )
    )


try:
    import Webpage_library as page_lib  # type: ignore
    _raw_page_map = getattr(page_lib, "page", None)
except (ImportError, AttributeError):
    _raw_page_map = None


def _build_page_map() -> dict[str, str]:
    """Build a safe page map from external library and defaults."""
    page_map = _default_page_map()
    if _raw_page_map is None:
        return page_map

    try:
        candidate_map = dict(_raw_page_map)
    except (TypeError, ValueError):
        logger.debug("Ignoring malformed page library data")
        return page_map

    for name, url in candidate_map.items():
        if not isinstance(name, str) or not isinstance(url, str):
            continue
        safe_url = _safe_url(url)
        if safe_url is not None:
            page_map[name.strip().lower()] = safe_url

    return page_map


PAGE_MAP = _build_page_map()


def get_page_map() -> dict[str, str]:
    """Return a copy of the assistant page map."""
    return dict(PAGE_MAP)


# ---------------------------------------------------------------------------
# Browser helper (unchanged from original)
# ---------------------------------------------------------------------------

def open_url_in_browser(url: str) -> tuple[bool, str]:
    """Open a URL in a new browser tab on the machine running the backend."""
    safe_url = _safe_url(url)
    if safe_url is None:
        return False, "The URL is invalid or unsafe."

    try:
        opened = webbrowser.open_new_tab(safe_url)
        if opened:
            return True, f"Opening: {safe_url}"
        return False, "Could not open the browser tab."
    except Exception as exc:
        logger.exception("Failed to open browser URL")
        return False, f"Failed to open URL: {exc}"


# ---------------------------------------------------------------------------
# Local Ollama LLM (replaces Gemini)
# ---------------------------------------------------------------------------

_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")

_SOFIA_SYSTEM_PROMPT = (
    "You are SOFIA, a helpful, friendly AI assistant. "
    "Answer questions concisely and naturally. "
    "If you don't know something, say so honestly."
)


def ask_ollama(prompt: str, history: list[dict[str, Any]] | None = None) -> str:
    """
    Send *prompt* to the locally running Ollama server and return the response.

    This is the backend's synchronous fallback for conversational chat when the
    Desktop Agent is not connected.  Tool-calling is handled by the Desktop Agent
    (agent_loop.py); this function only handles plain conversational responses.

    Uses environment variables:
        OLLAMA_BASE_URL  (default: http://localhost:11434)
        OLLAMA_MODEL     (default: qwen2.5:7b-instruct)
    """
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _SOFIA_SYSTEM_PROMPT}
    ]

    for turn in (history or [])[-10:]:
        role = str(turn.get("role", "user")).strip().lower()
        content = str(turn.get("content", "")).strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": prompt.strip()})

    payload: dict[str, Any] = {
        "model": _OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
    }

    try:
        response = _requests.post(
            f"{_OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=90,
        )
        response.raise_for_status()
        data = response.json()
        text = data.get("message", {}).get("content", "").strip()
        return text or "I didn't get a response from the local AI model."

    except _requests.exceptions.ConnectionError:
        logger.error("Cannot connect to Ollama at %s", _OLLAMA_BASE_URL)
        return (
            "The local AI model is not running. "
            "Please start Ollama with: ollama serve"
        )
    except _requests.exceptions.Timeout:
        logger.error("Ollama request timed out.")
        return "The local AI model took too long to respond. Please try again."
    except _requests.exceptions.HTTPError as exc:
        logger.error("Ollama HTTP error: %s", exc)
        return f"Local AI model returned an error: {exc}"
    except Exception as exc:
        logger.exception("Unexpected error calling Ollama")
        return f"Local AI error: {exc}"


# ---------------------------------------------------------------------------
# News API (unchanged from original)
# ---------------------------------------------------------------------------

def get_news() -> str:
    """
    Fetch top 5 news headlines from the News API.

    Uses environment variable: NEWS_API_KEY
    """
    api_key = _read_env_key("NEWS_API_KEY")

    if not api_key:
        return (
            "News service is not configured yet. "
            "Set the NEWS_API_KEY environment variable to enable it."
        )

    try:
        url = "https://newsapi.org/v2/top-headlines"
        params = {
            "country": "in",
            "pageSize": 5,
            "apiKey": api_key,
        }

        response = _requests.get(url, params=params, timeout=5)
        response.raise_for_status()

        data = response.json()
        articles = data.get("articles", [])
        if not articles:
            return "No news articles found."

        headlines = []
        for i, article in enumerate(articles, 1):
            title = article.get("title", "No title")
            source = article.get("source", {}).get("name", "Unknown")
            headlines.append(f"{i}. {title} ({source})")

        return "Here are the latest headlines:\n\n" + "\n".join(headlines)

    except _requests.exceptions.Timeout:
        logger.error("News API request timed out")
        return "News service is taking too long. Please try again."
    except _requests.exceptions.RequestException as exc:
        logger.exception("News API request failed")
        return f"News service is temporarily unavailable. Error: {exc}"
    except Exception as exc:
        logger.exception("News parsing failed")
        return f"Failed to process news. Error: {exc}"
