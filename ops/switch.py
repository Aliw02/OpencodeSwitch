"""`ops switch` / `ops current` / `ops rotate` - the actual key swap."""

from __future__ import annotations

from ops import opencode, paths, store, ui


def switch(name: str | None, as_json: bool = False) -> int:
    st = store.load()
    if not st.accounts:
        ui.fail("no accounts stored - run: ops account add <name> <key>")
        return 1

    if name is None:
        current = opencode.current_key()
        options = []
        for a in st.accounts:
            tag = " (active)" if a.name == st.active else ""
            drift = "  ← auth.json differs" if a.name == st.active and current and current != a.key else ""
            options.append(f"{a.name}{tag}{drift}")
        chosen = ui.pick(options, "Switch to which account?")
        if not chosen:
            ui.info("cancelled")
            return 1
        name = chosen.split("  ")[0].split(" (")[0]

    try:
        acct = st.get(name)
    except store.StoreError as exc:
        ui.fail(str(exc))
        return 1

    others = opencode.other_providers()
    backup = opencode.write_key(acct.key)
    st.set_active(acct.name)
    store.save(st)
    store.append_history("switch", acct.name, {"preserved": others})

    if as_json:
        import json

        print(json.dumps({"active": acct.name, "backup": str(backup), "preserved": others}))
        return 0

    ui.ok(f"active account: {ui.bold(acct.name)}")
    ui.info(f"key {ui.mask_key(acct.key)} written to {paths.auth_file()}")
    ui.info(f"backup: {backup}")
    if others:
        ui.info(f"untouched providers: {', '.join(others)}")
    ui.info("sessions unchanged - resume with: opencode -c")
    return 0


def current(as_json: bool = False) -> int:
    st = store.load()
    key = opencode.current_key()
    acct = st.find_by_key(key) if key else None
    active_name = acct.name if acct else st.active
    drift = bool(key and st.active and acct is None) or bool(
        key and acct and st.active and acct.name != st.active
    )

    if as_json:
        import json

        print(json.dumps({
            "active": active_name,
            "auth_json_key": bool(key),
            "drift": drift,
            "stored": st.names(),
        }))
        return 0

    if not key:
        ui.fail(f"no Zen key in {paths.auth_file()}")
        return 1
    ui.ok(f"active: {ui.bold(active_name or '(unknown - key not in store)')}")
    ui.info(f"key in auth.json: {ui.mask_key(key)}")
    if drift:
        ui.fail("drift: auth.json key does not match the stored active account")
        ui.info("fix with: ops switch <name>   or capture it: ops account import <name>")
        return 1
    return 0


def rotate() -> int:
    """Round-robin - the button you press after hitting a limit."""
    st = store.load()
    if len(st.accounts) < 2:
        ui.fail("need at least 2 accounts to rotate")
        return 1
    previous = st.active
    acct = st.next_account()
    backup = opencode.write_key(acct.key)
    store.save(st)
    store.append_history("rotate", acct.name, {"from": previous})
    ui.ok(f"rotated: {previous} -> {ui.bold(acct.name)}")
    ui.info(f"backup: {backup}")
    ui.info("sessions unchanged - resume with: opencode -c")
    return 0
