"""`ops account ...` subcommands."""

from __future__ import annotations

import getpass
import json

from ops import opencode, paths, store, ui, zen


def add(name: str, key: str | None, skip_validate: bool = False) -> int:
    if not key:
        key = getpass.getpass(f"Zen API key for '{name}': ").strip()
    if not key:
        ui.fail("no key provided")
        return 1

    st = store.load()
    if name in st.names():
        ui.fail(f"account '{name}' already exists")
        return 1
    if st.find_by_key(key):
        ui.fail("this API key is already stored")
        return 1

    if not skip_validate:
        ui.info("checking key against Zen (no tokens spent)…")
        try:
            result = zen.check(key)
        except zen.ZenError as exc:
            ui.fail(str(exc))
            return 2
        if result.status == "invalid":
            ui.fail(f"rejected by Zen: {result.detail}")
            return 1
        if result.status == "no_access":
            ui.warn(result.detail)
        elif result.status == "unverified":
            ui.warn(f"could not verify: {result.detail}")
        else:
            ui.ok(f"key accepted ({result.detail})")

    st.add(name, key)
    store.save(st)
    store.append_history("add", name)
    ui.ok(f"added '{name}'" + ("" if st.active != name else " (now active)"))
    return 0


def list_accounts(as_json: bool = False) -> int:
    st = store.load()
    if not st.accounts:
        ui.info("no accounts yet - run: ops account add <name> <key>")
        return 0

    if as_json:
        print(json.dumps({"active": st.active, "accounts": [a.to_dict() for a in st.accounts]}, indent=2))
        return 0

    rows = []
    for a in st.accounts:
        marker = ui.green("*") if a.name == st.active else " "
        drift = ""
        current = opencode.current_key()
        if a.name == st.active and current and current != a.key:
            drift = ui.yellow(" (auth.json drift)")
        rows.append([marker, a.name, ui.mask_key(a.key), a.last_used or "-", drift])
    print(ui.table(["", "NAME", "KEY", "LAST USED", ""], rows))
    return 0


def remove(name: str, force: bool) -> int:
    st = store.load()
    try:
        st.remove(name, force=force)
    except store.StoreError as exc:
        ui.fail(str(exc))
        return 1
    store.save(st)
    store.append_history("remove", name)
    ui.ok(f"removed '{name}'")
    return 0


def rename(old: str, new: str) -> int:
    st = store.load()
    try:
        st.rename(old, new)
    except store.StoreError as exc:
        ui.fail(str(exc))
        return 1
    store.save(st)
    store.append_history("rename", old, {"to": new})
    ui.ok(f"renamed '{old}' -> '{new}'")
    return 0


def import_current(name: str) -> int:
    """Capture the key currently sitting in auth.json as a named account."""
    key = opencode.current_key()
    if not key:
        ui.fail(f"no Zen key found in {paths.auth_file()}")
        return 1
    st = store.load()
    if st.find_by_key(key):
        existing = st.find_by_key(key)
        ui.fail(f"key already stored as '{existing.name}'")
        return 1
    if name in st.names():
        ui.fail(f"account '{name}' already exists")
        return 1
    st.add(name, key)
    st.active = name
    store.save(st)
    store.append_history("import", name)
    ui.ok(f"imported current auth.json key as '{name}'")
    return 0
