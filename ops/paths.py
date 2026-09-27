"""Locate OpenCode's config and data directories.

Mirrors OpenCode's own resolution (xdg-basedir) so `ops` finds the same
files OpenCode writes, on Windows, macOS and Linux.
"""

from __future__ import annotations

import os
from pathlib import Path

# OpenCode provider id for Zen (models are referenced as opencode/<model-id>)
ZEN_PROVIDER = "opencode"

# Zen public API, used only to validate a key before storing it.
ZEN_MODELS_URL = "https://opencode.ai/zen/v1/models"


def _home() -> Path:
    return Path(os.path.expanduser("~"))


def data_dir() -> Path:
    """Directory holding auth.json, storage/, logs."""
    explicit = os.environ.get("OPENCODE_DATA_DIR")
    if explicit:
        return Path(os.path.expanduser(explicit))
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(os.path.expanduser(xdg)) / "opencode"
    return _home() / ".local" / "share" / "opencode"


def config_dir() -> Path:
    """Directory holding opencode.json, plugins/, and our accounts file."""
    explicit = os.environ.get("OPENCODE_CONFIG_DIR")
    if explicit:
        return Path(os.path.expanduser(explicit))
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(os.path.expanduser(xdg)) / "opencode"
    return _home() / ".config" / "opencode"


def auth_file() -> Path:
    return data_dir() / "auth.json"


def auth_backup_file() -> Path:
    return data_dir() / "auth.json.bak"


def accounts_file() -> Path:
    return config_dir() / "zen-accounts.json"


def history_file() -> Path:
    return config_dir() / "zen-history.jsonl"


def opencode_installed() -> bool:
    """True if the opencode executable is on PATH."""
    import shutil

    return shutil.which("opencode") is not None
