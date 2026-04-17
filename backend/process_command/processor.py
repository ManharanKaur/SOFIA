from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import quote_plus

from support_functions.helpers import ask_ai, get_news, get_page_map, open_url_in_browser

logger = logging.getLogger(__name__)

MAX_COMMAND_LENGTH = 500
_SEARCH_PREFIXES = ("search", "google", "look up", "find")
_NEWS_KEYWORDS = ("news", "headlines", "latest")


def _normalize(command: str) -> str:
    """Normalize command text for simple intent matching."""

    return re.sub(r"\s+", " ", command.strip().lower())


def _validate_command(command: str) -> str:
    """Validate command length and normalize text."""

    cleaned_command = command.strip()
    if not cleaned_command:
        return ""
    if len(cleaned_command) > MAX_COMMAND_LENGTH:
        return "__too_long__"
    return _normalize(cleaned_command)


def _extract_prefixed_argument(command: str, prefixes: tuple[str, ...]) -> tuple[str | None, str | None]:
    """Return the matched prefix and its argument, preferring longer prefixes first."""

    for prefix in sorted(set(prefixes), key=len, reverse=True):
        if command == prefix:
            return prefix, ""
        prefix_with_space = f"{prefix} "
        if command.startswith(prefix_with_space):
            return prefix, command[len(prefix_with_space) :].strip()
    return None, None


def _build_search_url(query: str) -> str:
    """Build a safe Google search URL for the provided query."""

    return f"https://www.google.com/search?q={quote_plus(query)}"


def _normalize_open_target(target: str) -> str:
    """Normalize free-form open target into an HTTP URL when possible."""

    t = target.strip()
    if t.startswith(("http://", "https://")):
        return t

    # Basic domain support, e.g. "youtube.com" -> "https://youtube.com"
    if "." in t and " " not in t:
        return f"https://{t}"

    return ""


def _build_ai_prompt(command: str) -> str:
    """Create a structured prompt to keep Sofia's tone consistent and friendly."""

    return (
        "You are Sofia, a helpful and friendly AI assistant.\n\n"
        f"User: {command}\n\n"
        "Respond naturally and helpfully."
    )


def _respond(
    action: str,
    message: str,
    *,
    url: str | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a response payload and log the resolved command action."""

    logger.info("command_action=%s", action)
    response: dict[str, Any] = {"action": action, "message": message}
    if url is not None:
        response["url"] = url
    if data is not None:
        response["data"] = data
    return response


async def process_text_command(command: str) -> dict[str, Any]:
    """Process a natural-language command and return a structured response."""

    c = _validate_command(command)
    logger.info("command_received length=%s", len(command))

    if not c:
        return _respond("none", "Please type a command.")

    if c == "__too_long__":
        return _respond("error", f"Command is too long. Maximum length is {MAX_COMMAND_LENGTH} characters.")

    page_map = get_page_map()

    # Intent 1: open known websites.
    open_prefix, page_to_open = _extract_prefixed_argument(c, ("open",))
    if open_prefix is not None:
        if not page_to_open:
            return _respond("error", "Please tell me which page to open.")

        url = page_map.get(page_to_open) or _normalize_open_target(page_to_open)
        if url:
            ok, message = open_url_in_browser(url)
            return _respond("open_url" if ok else "error", message, url=url)
        return _respond("error", f"I cannot find '{page_to_open}' in the page library.")

    # Intent 2: web search.
    search_prefix, query = _extract_prefixed_argument(c, _SEARCH_PREFIXES)
    if search_prefix is not None:
        if not query:
            return _respond("error", "Please provide something to search for.")
        search_url = _build_search_url(query)
        return _respond("search", f"Searching for {query}: {search_url}", url=search_url)

    # Intent 3: simulate music play response.
    play_prefix, song = _extract_prefixed_argument(c, ("play",))
    if play_prefix is not None:
        if not song:
            return _respond("error", "Please tell me a song name.")
        return _respond("play_song", f"Playing {song} (simulated).", data={"song": song})

    # Intent 4: fetch news headlines.
    if any(keyword in c for keyword in _NEWS_KEYWORDS):
        news_response = get_news()
        return _respond("news", news_response)

    # Fallback: unknown commands are handled by the AI assistant.
    ai_prompt = _build_ai_prompt(command.strip())
    ai_answer = ask_ai(ai_prompt)
    return _respond("chat", str(ai_answer))
