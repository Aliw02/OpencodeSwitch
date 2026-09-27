"""Persist the list of Zen accounts.

File: <config>/zen-accounts.json   (mode 0600)
Shape:
    {"version": 1, "active": "aliweyabood",
     "accounts": [{"name", "key", "created", "last_used"}]}
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ops import paths

VERSION = 1


class StoreError(Exception):
    """User-facing storage problem (bad input, missing file, duplicate)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Account:
    name: str
    key: str
    created: str = field(default_factory=_now)
    last_used: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "key": self.key,
            "created": self.created,
            "last_used": self.last_used,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Account":
        return cls(
            name=raw["name"],
            key=raw["key"],
            created=raw.get("created", _now()),
            last_used=raw.get("last_used"),
        )


@dataclass
class Store:
    active: str | None = None
    accounts: list[Account] = field(default_factory=list)

    # -- lookup ---------------------------------------------------------
    def get(self, name: str) -> Account:
        for acct in self.accounts:
            if acct.name == name:
                return acct
        raise StoreError(f"no account named '{name}'")

    def find_by_key(self, key: str) -> Account | None:
        for acct in self.accounts:
            if acct.key == key:
                return acct
        return None

    def names(self) -> list[str]:
        return [a.name for a in self.accounts]

    def active_account(self) -> Account | None:
        if not self.active:
            return None
        for acct in self.accounts:
            if acct.name == self.active:
                return acct
        return None

    # -- mutation -------------------------------------------------------
    def add(self, name: str, key: str) -> Account:
        if not name.strip():
            raise StoreError("account name cannot be empty")
        if any(c.isspace() for c in name):
            raise StoreError("account name cannot contain spaces")
        if self.find_by_key(key):
            raise StoreError("this API key is already stored")
        if name in self.names():
            raise StoreError(f"account '{name}' already exists")
        acct = Account(name=name, key=key)
        self.accounts.append(acct)
        if self.active is None:
            self.active = name
        return acct

    def remove(self, name: str, force: bool = False) -> None:
        acct = self.get(name)
        if name == self.active and not force:
            raise StoreError(f"'{name}' is active - switch away first or pass --force")
        self.accounts.remove(acct)
        if self.active == name:
            self.active = self.accounts[0].name if self.accounts else None

    def rename(self, old: str, new: str) -> None:
        if any(c.isspace() for c in new):
            raise StoreError("account name cannot contain spaces")
        if new in self.names():
            raise StoreError(f"account '{new}' already exists")
        acct = self.get(old)
        acct.name = new
        if self.active == old:
            self.active = new

    def set_active(self, name: str) -> Account:
        acct = self.get(name)
        acct.last_used = _now()
        self.active = name
        return acct

    def next_account(self) -> Account:
        """Round-robin: the account after the current active one."""
        if not self.accounts:
            raise StoreError("no accounts stored - run: ops account add <name> <key>")
        if not self.active:
            return self.set_active(self.accounts[0].name)
        idx = self.names().index(self.active)
        return self.set_active(self.accounts[(idx + 1) % len(self.accounts)].name)


# -- persistence ---------------------------------------------------------

def _atomic_write(path: Path, text: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".ops-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
        try:
            os.chmod(path, mode)
        except OSError:
            pass  # best effort on Windows
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def load() -> Store:
    path = paths.accounts_file()
    if not path.exists():
        return Store()
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StoreError(f"cannot read {path}: {exc}") from exc
    return Store(
        active=raw.get("active"),
        accounts=[Account.from_dict(a) for a in raw.get("accounts", [])],
    )


def save(store: Store) -> None:
    payload = {
        "version": VERSION,
        "active": store.active,
        "accounts": [a.to_dict() for a in store.accounts],
    }
    _atomic_write(paths.accounts_file(), json.dumps(payload, indent=2) + "\n")


# -- history -------------------------------------------------------------

def append_history(action: str, name: str, extra: dict[str, Any] | None = None) -> None:
    entry = {"at": _now(), "action": action, "account": name}
    if extra:
        entry.update(extra)
    path = paths.history_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def read_history(limit: int = 20) -> list[dict[str, Any]]:
    path = paths.history_file()
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-limit:][::-1]
