"""
tool_executor.py
----------------
Executes validated, whitelisted tool calls using macOS-native mechanisms.

Security rules
--------------
- Only tools listed in tool_registry.py may be executed.
- Arguments are validated against the tool's JSON schema before any execution.
- subprocess is called ONLY with fixed argument lists (no shell=True with
  user-supplied strings).
- AppleScript templates use only predefined patterns with escaped arguments.
- The executor never accepts a generic shell command.
"""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlsplit, urlunsplit

from tool_registry import get_tool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Safe argument helpers
# ---------------------------------------------------------------------------

def _safe_url(url: str) -> str | None:
    """Return a sanitised HTTPS/HTTP URL or None if unsafe."""
    try:
        parsed = urlsplit(url.strip())
    except Exception:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


_ALLOWED_BROWSERS: dict[str, str] = {
    "chrome": "Google Chrome",
    "safari": "Safari",
    "firefox": "Firefox",
}

_ALLOWED_APPS: dict[str, str] = {
    "spotify": "Spotify",
    "finder": "Finder",
    "calendar": "Calendar",
    "notes": "Notes",
    "mail": "Mail",
    "terminal": "Terminal",
    "textedit": "TextEdit",
    "calculator": "Calculator",
    "maps": "Maps",
    "chrome": "Google Chrome",
    "safari": "Safari",
    "firefox": "Firefox",
}

_APPLESCRIPT_SAFE_RE = re.compile(r'[^a-zA-Z0-9 \-_\.\,\!\?]')


def _escape_applescript(value: str) -> str:
    """Strip any characters that should not appear in an AppleScript string."""
    return _APPLESCRIPT_SAFE_RE.sub("", value)[:200]


# ---------------------------------------------------------------------------
# Executor dispatch
# ---------------------------------------------------------------------------

def execute_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Execute *tool_name* with *arguments* and return a result dict.

    Returns
    -------
    dict with keys:
        success (bool)
        message (str)  — human-readable outcome for TTS/display
        data    (dict) — optional extra data
    """
    tool_def = get_tool(tool_name)
    if tool_def is None:
        return _fail(f"Unknown tool: {tool_name!r}")

    logger.info("Executing tool '%s' with args %s", tool_name, arguments)

    handlers: dict[str, Any] = {
        "open_browser":     _open_browser,
        "open_url":         _open_url,
        "open_app":         _open_app,
        "play_spotify":     _play_spotify,
        "pause_spotify":    _pause_spotify,
        "next_spotify":     _next_spotify,
        "previous_spotify": _previous_spotify,
        "search_spotify":   _search_spotify,
        "control_volume":   _control_volume,
        "find_file":        _find_file,
        "search_web":       _search_web,
    }

    handler = handlers.get(tool_name)
    if handler is None:
        return _fail(f"No handler implemented for tool: {tool_name!r}")

    try:
        return handler(arguments)
    except Exception as exc:
        logger.exception("Tool '%s' raised an exception", tool_name)
        return _fail(f"Tool execution error: {exc}")


# ---------------------------------------------------------------------------
# Result helpers
# ---------------------------------------------------------------------------

def _ok(message: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"success": True, "message": message, "data": data or {}}


def _fail(message: str) -> dict[str, Any]:
    return {"success": False, "message": message, "data": {}}


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def _open_browser(args: dict[str, Any]) -> dict[str, Any]:
    browser_key = str(args.get("browser", "")).lower()
    app_name = _ALLOWED_BROWSERS.get(browser_key)
    if not app_name:
        return _fail(f"Unsupported browser: {args.get('browser')!r}")
    result = subprocess.run(["open", "-a", app_name], capture_output=True, timeout=10)
    if result.returncode == 0:
        return _ok(f"Opened {app_name}.")
    return _fail(f"Could not open {app_name}: {result.stderr.decode()}")


def _open_url(args: dict[str, Any]) -> dict[str, Any]:
    raw_url = str(args.get("url", ""))
    safe = _safe_url(raw_url)
    if not safe:
        return _fail(f"URL is invalid or unsafe: {raw_url!r}")
    result = subprocess.run(["open", safe], capture_output=True, timeout=10)
    if result.returncode == 0:
        return _ok(f"Opened {safe}.")
    return _fail(f"Could not open URL: {result.stderr.decode()}")


def _open_app(args: dict[str, Any]) -> dict[str, Any]:
    raw_name = str(args.get("app_name", "")).lower().strip()
    app_name = _ALLOWED_APPS.get(raw_name)
    if not app_name:
        return _fail(
            f"I don't have permission to open {args.get('app_name')!r}. "
            f"Supported apps: {', '.join(_ALLOWED_APPS.values())}."
        )
    result = subprocess.run(["open", "-a", app_name], capture_output=True, timeout=10)
    if result.returncode == 0:
        return _ok(f"Opened {app_name}.")
    return _fail(f"Could not open {app_name}: {result.stderr.decode()}")


def _run_applescript(script: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        timeout=15,
    )


def _play_spotify(args: dict[str, Any]) -> dict[str, Any]:
    query = _escape_applescript(str(args.get("query", "")))
    if not query:
        return _fail("Please provide a search query for Spotify.")

    # First ensure Spotify is open.
    subprocess.run(["open", "-a", "Spotify"], capture_output=True, timeout=10)

    # Use Spotify URI search via AppleScript.
    search_uri = f"spotify:search:{query.replace(' ', '%20')}"
    script = (
        f'tell application "Spotify"\n'
        f'  activate\n'
        f'  play track "{search_uri}"\n'
        f'end tell'
    )
    result = _run_applescript(script)
    if result.returncode == 0:
        return _ok(f"Playing '{query}' on Spotify.")
    # Fallback: open Spotify search in browser.
    search_url = f"https://open.spotify.com/search/{quote_plus(query)}"
    subprocess.run(["open", search_url], capture_output=True, timeout=10)
    return _ok(f"Opened Spotify search for '{query}' in your browser.")


def _pause_spotify(_args: dict[str, Any]) -> dict[str, Any]:
    result = _run_applescript('tell application "Spotify" to pause')
    if result.returncode == 0:
        return _ok("Paused Spotify.")
    return _fail("Could not pause Spotify. Is Spotify running?")


def _next_spotify(_args: dict[str, Any]) -> dict[str, Any]:
    result = _run_applescript('tell application "Spotify" to next track')
    if result.returncode == 0:
        return _ok("Skipped to next track.")
    return _fail("Could not skip track. Is Spotify running?")


def _previous_spotify(_args: dict[str, Any]) -> dict[str, Any]:
    result = _run_applescript('tell application "Spotify" to previous track')
    if result.returncode == 0:
        return _ok("Went back to the previous track.")
    return _fail("Could not go to previous track. Is Spotify running?")


def _search_spotify(args: dict[str, Any]) -> dict[str, Any]:
    query = _escape_applescript(str(args.get("query", "")))
    if not query:
        return _fail("Please provide a search query.")
    search_url = f"https://open.spotify.com/search/{quote_plus(query)}"
    result = subprocess.run(["open", search_url], capture_output=True, timeout=10)
    if result.returncode == 0:
        return _ok(f"Opened Spotify search for '{query}'.")
    return _fail("Could not open Spotify search.")


def _control_volume(args: dict[str, Any]) -> dict[str, Any]:
    action = str(args.get("action", "")).lower()
    level = args.get("level")

    if action == "set":
        if level is None or not (0 <= int(level) <= 100):
            return _fail("Please specify a volume level between 0 and 100.")
        script = f"set volume output volume {int(level)}"
    elif action == "increase":
        script = "set volume output volume ((output volume of (get volume settings)) + 10)"
    elif action == "decrease":
        script = "set volume output volume ((output volume of (get volume settings)) - 10)"
    elif action == "mute":
        script = "set volume output muted true"
    elif action == "unmute":
        script = "set volume output muted false"
    else:
        return _fail(f"Unknown volume action: {action!r}")

    result = _run_applescript(script)
    if result.returncode == 0:
        return _ok(f"Volume {action} executed.")
    return _fail(f"Volume control failed: {result.stderr.decode()}")


def _find_file(args: dict[str, Any]) -> dict[str, Any]:
    filename = str(args.get("filename", "")).strip()
    if not filename or len(filename) < 2:
        return _fail("Please provide a longer filename to search for.")

    home = Path.home()
    matches: list[str] = []
    try:
        for path in home.rglob(f"*{filename}*"):
            if path.is_file():
                matches.append(str(path))
            if len(matches) >= 10:
                break
    except PermissionError:
        pass

    if not matches:
        return _ok(f"No files found matching '{filename}'.", {"matches": []})
    return _ok(
        f"Found {len(matches)} file(s) matching '{filename}'.",
        {"matches": matches},
    )


def _search_web(args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query", "")).strip()
    if not query:
        return _fail("Please provide a search query.")
    url = f"https://www.google.com/search?q={quote_plus(query)}"
    result = subprocess.run(["open", url], capture_output=True, timeout=10)
    if result.returncode == 0:
        return _ok(f"Searching the web for '{query}'.")
    return _fail("Could not open web search.")
