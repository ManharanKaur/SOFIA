"""
permission_groups.py
--------------------
Defines every permission group available in the SOFIA Desktop Agent.

Design principles
-----------------
- Least privilege: each group covers only the minimal set of tools.
- Sensitive operations ALWAYS require per-request re-confirmation even when
  the broader group is already granted.
- No group implicitly grants another group.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet


@dataclass(frozen=True)
class PermissionGroup:
    """A named collection of tools that share a single user consent gate."""

    key: str
    label: str
    description: str
    tools: FrozenSet[str]
    # Tools inside this group that still need per-call re-confirmation.
    sensitive_tools: FrozenSet[str] = field(default_factory=frozenset)


# ---------------------------------------------------------------------------
# Group definitions — add new groups here; agent_loop discovers them via
# PERMISSION_GROUPS_BY_KEY.
# ---------------------------------------------------------------------------

BROWSER_CONTROL = PermissionGroup(
    key="browser_control",
    label="Browser Control",
    description=(
        "Allow SOFIA to open Chrome, Safari, or Firefox and navigate to URLs."
    ),
    tools=frozenset(
        {"open_browser", "open_url"}
    ),
)

APP_CONTROL = PermissionGroup(
    key="app_control",
    label="Application Control",
    description=(
        "Allow SOFIA to open supported applications on your Mac "
        "(e.g. Finder, Calendar, Notes)."
    ),
    tools=frozenset({"open_app"}),
)

SPOTIFY_CONTROL = PermissionGroup(
    key="spotify_control",
    label="Spotify Control",
    description=(
        "Allow SOFIA to control Spotify — play, pause, skip, "
        "and search for music."
    ),
    tools=frozenset(
        {
            "play_spotify",
            "pause_spotify",
            "next_spotify",
            "previous_spotify",
            "search_spotify",
        }
    ),
)

SYSTEM_CONTROLS = PermissionGroup(
    key="system_controls",
    label="System Controls",
    description=(
        "Allow SOFIA to adjust system volume and display brightness."
    ),
    tools=frozenset({"control_volume"}),
)

FILE_ACCESS = PermissionGroup(
    key="file_access",
    label="File Access",
    description="Allow SOFIA to search for files by name in your home folder.",
    tools=frozenset({"find_file"}),
    sensitive_tools=frozenset({"find_file"}),  # always reconfirm
)

WEB_SEARCH = PermissionGroup(
    key="web_search",
    label="Web Search",
    description=(
        "Allow SOFIA to build a search URL and open it in your browser. "
        "No local data is accessed."
    ),
    tools=frozenset({"search_web"}),
)

# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

ALL_GROUPS: list[PermissionGroup] = [
    BROWSER_CONTROL,
    APP_CONTROL,
    SPOTIFY_CONTROL,
    SYSTEM_CONTROLS,
    FILE_ACCESS,
    WEB_SEARCH,
]

# Map: group_key -> PermissionGroup
PERMISSION_GROUPS_BY_KEY: dict[str, PermissionGroup] = {
    g.key: g for g in ALL_GROUPS
}

# Map: tool_name -> owning PermissionGroup
TOOL_TO_PERMISSION_GROUP: dict[str, PermissionGroup] = {
    tool: group
    for group in ALL_GROUPS
    for tool in group.tools
}


def get_group_for_tool(tool_name: str) -> PermissionGroup | None:
    """Return the permission group that owns *tool_name*, or ``None``."""
    return TOOL_TO_PERMISSION_GROUP.get(tool_name)


def is_sensitive(tool_name: str) -> bool:
    """Return ``True`` when *tool_name* needs per-call re-confirmation."""
    group = get_group_for_tool(tool_name)
    return group is not None and tool_name in group.sensitive_tools
