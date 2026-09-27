"""`ops test` / `ops doctor` / `ops run` / `ops history`."""

from __future__ import annotations

import json
import os
import shutil
import sys

from ops import opencode, paths, store, ui, zen


def test(name: str | None) -> int:
    st = store.load()
    if name:
        try:
            targets = [st.get(name)]
        except store.StoreError as exc:
            ui.fail(str(exc))
            return 1
    else:
        targets = st.accounts
        if not targets:
            ui.fail("no accounts stored")
            return 1

    failed = 0
    for acct in targets:
        ui.info(f"testing {acct.name}…")
        try:
            result = zen.check(acct.key)
        except zen.ZenError as exc:
            ui.fail(f"{acct.name}: {exc}")
            failed += 1
            continue
        if result.status == "invalid":
            ui.fail(f"{acct.name}: {result.detail}")
            failed += 1
        elif result.status == "no_access":
            ui.warn(f"{acct.name}: {result.detail}")
        elif result.status == "ok":
            ui.ok(f"{acct.name}: key accepted")
        else:
            ui.warn(f"{acct.name}: {result.detail}")
    return 2 if failed else 0


def doctor() -> int:
    problems = 0

    print(ui.bold("ops doctor"))
    print()

    py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info < (3, 10):
        ui.fail(f"python {py} - needs 3.10+")
        problems += 1
    else:
        print(f"  {ui.green(ui.CHECK)} python        {py}")

    if paths.opencode_installed():
        print(f"  {ui.green(ui.CHECK)} opencode      {shutil.which('opencode')}")
    else:
        print(f"  {ui.yellow(ui.WARN)} opencode      not on PATH")
        problems += 1

    auth = paths.auth_file()
    if auth.exists():
        print(f"  {ui.green(ui.CHECK)} auth.json     {auth}")
    else:
        print(f"  {ui.yellow(ui.WARN)} auth.json     missing at {auth}")
        problems += 1

    others = opencode.other_providers()
    print(f"  {ui.dim(ui.DOT)} providers     {', '.join(others) or '(none)'}")

    acct_file = paths.accounts_file()
    if acct_file.exists():
        print(f"  {ui.green(ui.CHECK)} accounts file {acct_file}")
    else:
        print(f"  {ui.yellow(ui.WARN)} accounts file missing at {acct_file}")

    st = store.load()
    print(f"  {ui.dim(ui.DOT)} accounts      {len(st.accounts)} stored, active = {st.active}")
    if not st.accounts:
        print(f"  {ui.yellow(ui.WARN)} run: ops account add <name> <key>")
        problems += 1

    bak = paths.auth_backup_file()
    if bak.exists():
        print(f"  {ui.green(ui.CHECK)} backup        {bak}")
    else:
        print(f"  {ui.dim(ui.DOT)} backup        (none yet)")

    print()
    if problems:
        print(ui.yellow(f"{problems} issue(s) found"))
        return 1
    print(ui.green("all checks passed"))
    return 0


def run(account: str | None, args: list[str]) -> int:
    """Switch (if asked), then exec opencode with the remaining args."""
    if account:
        code = _switch_quietly(account)
        if code:
            return code
    if not args:
        ui.fail("nothing to run - usage: ops run [--account x] -- opencode args")
        return 1
    target = args[0] if args[0] == "opencode" else "opencode"
    cmd = [target] + ([] if args[0] == "opencode" else args)
    exe = shutil.which(cmd[0])
    if not exe:
        ui.fail("opencode not found on PATH")
        return 1
    ui.info(f"exec: {' '.join(cmd)}")
    return os.spawnv(os.P_WAIT, exe, cmd)


def _switch_quietly(name: str) -> int:
    st = store.load()
    try:
        acct = st.get(name)
    except store.StoreError as exc:
        ui.fail(str(exc))
        return 1
    opencode.write_key(acct.key)
    st.set_active(acct.name)
    store.save(st)
    store.append_history("switch", acct.name, {"via": "run"})
    ui.ok(f"active: {acct.name}")
    return 0


def history(as_json: bool = False, limit: int = 20) -> int:
    rows = store.read_history(limit)
    if as_json:
        print(json.dumps(rows, indent=2))
        return 0
    if not rows:
        ui.info("no history yet")
        return 0
    print(ui.table(
        ["WHEN", "ACTION", "ACCOUNT", "DETAIL"],
        [[r.get("at", ""), r.get("action", ""), r.get("account", ""),
          ui.dim(", ".join(f"{k}={v}" for k, v in r.items() if k not in ("at", "action", "account")))]
         for r in rows],
    ))
    return 0
