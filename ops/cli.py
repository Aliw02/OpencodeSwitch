"""argparse wiring only. All logic lives in the owning module."""

from __future__ import annotations

import argparse
import sys

from ops import __version__
from ops import account as account_cmd
from ops import switch as switch_cmd
from ops import tools, ui


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ops",
        description="Switch between OpenCode Zen accounts without losing sessions.",
    )
    p.add_argument("-v", "--version", action="version", version=f"ops {__version__}")
    sub = p.add_subparsers(dest="group", required=True)

    # -- ops account ----------------------------------------------------
    acc = sub.add_parser("account", help="manage stored Zen accounts")
    acc_sub = acc.add_subparsers(dest="cmd", required=True)

    a_add = acc_sub.add_parser("add", help="add an account (validates the key)")
    a_add.add_argument("name", help="account name, no spaces")
    a_add.add_argument("key", nargs="?", help="Zen API key (prompted if omitted)")
    a_add.add_argument("--no-validate", action="store_true", help="skip the Zen API check")

    a_list = acc_sub.add_parser("list", help="list accounts")
    a_list.add_argument("--json", action="store_true")

    a_rm = acc_sub.add_parser("remove", help="delete an account")
    a_rm.add_argument("name")
    a_rm.add_argument("--force", action="store_true", help="allow removing the active account")

    a_ren = acc_sub.add_parser("rename", help="rename an account")
    a_ren.add_argument("old")
    a_ren.add_argument("new")

    a_imp = acc_sub.add_parser("import", help="store the key currently in auth.json")
    a_imp.add_argument("name")

    # -- ops switch / current / rotate ----------------------------------
    sw = sub.add_parser("switch", help="activate an account")
    sw.add_argument("name", nargs="?", help="account name (interactive picker if omitted)")
    sw.add_argument("--account", dest="account_opt", help="same as positional name")
    sw.add_argument("--json", action="store_true")

    cur = sub.add_parser("current", help="show the active account")
    cur.add_argument("--json", action="store_true")

    sub.add_parser("rotate", help="round-robin to the next account")

    # -- ops test / doctor / run / history --------------------------------
    tst = sub.add_parser("test", help="validate stored keys against Zen")
    tst.add_argument("name", nargs="?")

    sub.add_parser("doctor", help="check the environment")

    runp = sub.add_parser("run", help="switch, then run opencode")
    runp.add_argument("--account", help="switch to this account first")
    runp.add_argument("args", nargs=argparse.REMAINDER, help="args passed to opencode")

    his = sub.add_parser("history", help="recent switches")
    his.add_argument("--json", action="store_true")
    his.add_argument("-n", "--limit", type=int, default=20)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _dispatch(args)
    except KeyboardInterrupt:
        print()
        return 130


def _dispatch(args: argparse.Namespace) -> int:
    g, c = args.group, getattr(args, "cmd", None)

    if g == "account":
        if c == "add":
            return account_cmd.add(args.name, args.key, skip_validate=args.no_validate)
        if c == "list":
            return account_cmd.list_accounts(as_json=args.json)
        if c == "remove":
            return account_cmd.remove(args.name, args.force)
        if c == "rename":
            return account_cmd.rename(args.old, args.new)
        if c == "import":
            return account_cmd.import_current(args.name)

    if g == "switch":
        return switch_cmd.switch(args.name or args.account_opt, as_json=args.json)
    if g == "current":
        return switch_cmd.current(as_json=args.json)
    if g == "rotate":
        return switch_cmd.rotate()

    if g == "test":
        return tools.test(args.name)
    if g == "doctor":
        return tools.doctor()
    if g == "run":
        return tools.run(args.account, args.args)
    if g == "history":
        return tools.history(as_json=args.json, limit=args.limit)

    ui.fail(f"unknown command: {g}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
