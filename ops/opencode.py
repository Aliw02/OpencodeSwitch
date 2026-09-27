"""Read and write OpenCode's auth.json.

Only the Zen provider entry (`opencode`) is ever modified. Every other
provider already in the file is preserved byte-for-byte in meaning.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from ops import paths


class AuthError(Exception):
    pass


def read() -> dict[str, Any]:
    path = paths.auth_file()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuthError(f"cannot read {path}: {exc}") from exc


def current_key() -> str | None:
    """The Zen API key OpenCode will actually use right now."""
    entry = read().get(paths.ZEN_PROVIDER)
    if isinstance(entry, dict):
        key = entry.get("key")
        if isinstance(key, str) and key:
            return key
    return None


def write_key(key: str) -> Path:
    """Set the Zen key, backing up auth.json first. Returns the backup path."""
    path = paths.auth_file()
    data = read()
    backup = paths.auth_backup_file()

    if path.exists():
        try:
            shutil.copy2(path, backup)
        except OSError as exc:
            raise AuthError(f"cannot back up {path}: {exc}") from exc

    entry = data.get(paths.ZEN_PROVIDER)
    if not isinstance(entry, dict):
        entry = {"type": "api"}
    entry["type"] = "api"
    entry["key"] = key
    data[paths.ZEN_PROVIDER] = entry

    _atomic_write(path, json.dumps(data, indent=2) + "\n")
    return backup


def restore_backup() -> bool:
    """Put auth.json.bak back in place. Returns False if no backup exists."""
    backup = paths.auth_backup_file()
    if not backup.exists():
        return False
    shutil.copy2(backup, paths.auth_file())
    return True


def other_providers() -> list[str]:
    """Provider ids present in auth.json other than Zen - used to prove
    a switch did not disturb them."""
    return sorted(k for k in read() if k != paths.ZEN_PROVIDER)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".ops-auth-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
