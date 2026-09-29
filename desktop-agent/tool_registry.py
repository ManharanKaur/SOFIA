"""
tool_registry.py
----------------
Single source of truth for every tool the LLM may call.

Rules
-----
- The LLM sees ONLY the JSON schema in OLLAMA_TOOL_SCHEMAS.
- No ``exec``, no ``subprocess`` with arbitrary strings, no shell=True with
  user-supplied strings.  Only fixed, validated operations.
- Every tool maps to exactly one permission group key.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolDefinition:
    """Metadata that the agent uses to validate and route tool calls."""

    name: str
    permission_group: str        # must match a key in permission_groups.py
    description: str
    parameters: dict[str, Any]   # JSON-Schema object for parameter validation


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

OPEN_BROWSER = ToolDefinition(
    name="open_browser",
    permission_group="browser_control",
    description="Open a browser application by name (Chrome, Safari, Firefox).",
    parameters={
        "type": "object",
        "properties": {
            "browser": {
                "type": "string",
                "enum": ["Chrome", "Safari", "Firefox"],
                "description": "The browser to open.",
            }
        },
        "required": ["browser"],
    },
)

OPEN_URL = ToolDefinition(
    name="open_url",
    permission_group="browser_control",
    description="Open a specific URL in the default browser.",
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "A full HTTP or HTTPS URL to open.",
            }
        },
        "required": ["url"],
    },
)

OPEN_APP = ToolDefinition(
    name="open_app",
    permission_group="app_control",
    description=(
        "Open a macOS application by its common name. "
        "Supported: Spotify, Finder, Calendar, Notes, Mail, "
        "Terminal, TextEdit, Calculator, Maps."
    ),
    parameters={
        "type": "object",
        "properties": {
            "app_name": {
                "type": "string",
                "description": "The name of the application to open.",
            }
        },
        "required": ["app_name"],
    },
)

PLAY_SPOTIFY = ToolDefinition(
    name="play_spotify",
    permission_group="spotify_control",
    description=(
        "Search for and play a track, artist, playlist, or genre on Spotify. "
        "Examples: 'Shape of You', 'study music', 'The Weeknd'."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to search for and play on Spotify.",
            }
        },
        "required": ["query"],
    },
)

PAUSE_SPOTIFY = ToolDefinition(
    name="pause_spotify",
    permission_group="spotify_control",
    description="Pause Spotify playback.",
    parameters={"type": "object", "properties": {}, "required": []},
)

NEXT_SPOTIFY = ToolDefinition(
    name="next_spotify",
    permission_group="spotify_control",
    description="Skip to the next track on Spotify.",
    parameters={"type": "object", "properties": {}, "required": []},
)

PREVIOUS_SPOTIFY = ToolDefinition(
    name="previous_spotify",
    permission_group="spotify_control",
    description="Go back to the previous track on Spotify.",
    parameters={"type": "object", "properties": {}, "required": []},
)

SEARCH_SPOTIFY = ToolDefinition(
    name="search_spotify",
    permission_group="spotify_control",
    description="Search Spotify for tracks, artists, or albums and return results.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query for Spotify.",
            }
        },
        "required": ["query"],
    },
)

CONTROL_VOLUME = ToolDefinition(
    name="control_volume",
    permission_group="system_controls",
    description="Set or adjust the system volume.",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["set", "increase", "decrease", "mute", "unmute"],
                "description": "The volume action to perform.",
            },
            "level": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Volume level 0–100 (only for 'set' action).",
            },
        },
        "required": ["action"],
    },
)

FIND_FILE = ToolDefinition(
    name="find_file",
    permission_group="file_access",
    description=(
        "Search for a file by name in the user's home directory. "
        "Returns up to 10 matching paths."
    ),
    parameters={
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "File name or partial name to search for.",
            }
        },
        "required": ["filename"],
    },
)

SEARCH_WEB = ToolDefinition(
    name="search_web",
    permission_group="web_search",
    description="Open a Google search for the given query in the browser.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query.",
            }
        },
        "required": ["query"],
    },
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ALL_TOOLS: list[ToolDefinition] = [
    OPEN_BROWSER,
    OPEN_URL,
    OPEN_APP,
    PLAY_SPOTIFY,
    PAUSE_SPOTIFY,
    NEXT_SPOTIFY,
    PREVIOUS_SPOTIFY,
    SEARCH_SPOTIFY,
    CONTROL_VOLUME,
    FIND_FILE,
    SEARCH_WEB,
]

TOOLS_BY_NAME: dict[str, ToolDefinition] = {t.name: t for t in ALL_TOOLS}


# ---------------------------------------------------------------------------
# Ollama-compatible tool schema (sent in every inference request)
# ---------------------------------------------------------------------------

OLLAMA_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }
    for tool in ALL_TOOLS
]


def get_tool(name: str) -> ToolDefinition | None:
    """Look up a tool by name; returns ``None`` for unknown tools."""
    return TOOLS_BY_NAME.get(name)
