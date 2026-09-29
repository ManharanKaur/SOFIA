"""
permission_store.py
-------------------
Persistent, file-based store for user permission decisions.

Storage format
--------------
~/.sofia_permissions.json
{
    "browser_control": {"granted": true,  "remember": true},
    "spotify_control": {"granted": false, "remember": true},
    "file_access":     {"granted": true,  "remember": false}   <- session only
}

Rules
-----
- ``remember=True``  → decision persists across agent restarts.
- ``remember=False`` → decision is kept only for the current session
  (held in memory, never written to disk).
- Permissions that have never been asked about are not stored.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_STORE_PATH = Path.home() / ".sofia_permissions.json"


# ---------------------------------------------------------------------------
# In-memory session-only permissions (remember=False)
# ---------------------------------------------------------------------------
_session_permissions: dict[str, bool] = {}


# ---------------------------------------------------------------------------
# Disk helpers
# ---------------------------------------------------------------------------

def _load_disk_store() -> dict[str, Any]:
    """Read the on-disk permissions file.  Returns an empty dict on error."""
    if not _STORE_PATH.exists():
        return {}
    try:
        raw = _STORE_PATH.read_text(encoding="utf-8")
        return json.loads(raw)
    except (json.JSONDecodeError, OSError):
        logger.warning("Could not read permission store; starting fresh.")
        return {}


def _save_disk_store(store: dict[str, Any]) -> None:
    """Write the permissions dict to disk."""
    try:
        _STORE_PATH.write_text(json.dumps(store, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.error("Failed to persist permission store: %s", exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_granted(permission_key: str) -> bool:
    """
    Return ``True`` when the user has already granted *permission_key*.

    Checks session memory first, then the on-disk store.
    """
    # Check session-only grants first.
    if permission_key in _session_permissions:
        return _session_permissions[permission_key]

    # Then check persistent grants.
    store = _load_disk_store()
    entry = store.get(permission_key)
    if entry and isinstance(entry, dict):
        return bool(entry.get("granted", False))

    return False


def save_decision(
    permission_key: str,
    *,
    granted: bool,
    remember: bool,
) -> None:
    """
    Persist a permission decision made by the user.

    Parameters
    ----------
    permission_key:
        The group key (e.g. ``"browser_control"``).
    granted:
        ``True`` if the user approved; ``False`` if denied.
    remember:
        If ``True``, write to disk so the decision survives restarts.
        If ``False``, store in session memory only.
    """
    if remember:
        store = _load_disk_store()
        store[permission_key] = {"granted": granted, "remember": True}
        _save_disk_store(store)
        # Remove any conflicting session entry.
        _session_permissions.pop(permission_key, None)
        logger.info(
            "Permission '%s' %s (persisted).",
            permission_key,
            "GRANTED" if granted else "DENIED",
        )
    else:
        _session_permissions[permission_key] = granted
        logger.info(
            "Permission '%s' %s (session only).",
            permission_key,
            "GRANTED" if granted else "DENIED",
        )


def revoke(permission_key: str) -> None:
    """Remove a previously granted permission from both stores."""
    _session_permissions.pop(permission_key, None)
    store = _load_disk_store()
    if permission_key in store:
        del store[permission_key]
        _save_disk_store(store)
    logger.info("Permission '%s' revoked.", permission_key)


def all_permissions() -> dict[str, dict[str, Any]]:
    """Return a merged view of all stored permissions (disk + session)."""
    store = _load_disk_store()
    for key, granted in _session_permissions.items():
        store[key] = {"granted": granted, "remember": False}
    return store
