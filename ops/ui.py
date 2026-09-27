"""Terminal output helpers - zero dependencies, plain ANSI."""

from __future__ import annotations

import sys

_USE_COLOR = sys.stdout.isatty()

# Windows consoles default to cp1252, which cannot encode ✓/✗. Force UTF-8 so
# symbols render correctly both on a real console and when piped.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass


def _encodable(ch: str) -> bool:
    try:
        ch.encode(sys.stdout.encoding or "ascii")
        return True
    except (LookupError, UnicodeEncodeError):
        return False


CHECK = "✓" if _encodable("✓") else "+"
CROSS = "✗" if _encodable("✗") else "x"
WARN = "!" if _encodable("!") else "!"
DOT = "·" if _encodable("·") else "-"
BULLET = "→" if _encodable("→") else "->"


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def bold(t: str) -> str:
    return _c("1", t)


def green(t: str) -> str:
    return _c("32", t)


def red(t: str) -> str:
    return _c("31", t)


def yellow(t: str) -> str:
    return _c("33", t)


def dim(t: str) -> str:
    return _c("2", t)


def mask_key(key: str) -> str:
    """Never print a full credential."""
    if not key:
        return dim("(empty)")
    if len(key) <= 10:
        return red("(hidden)")
    return f"{key[:6]}…{key[-4:]}"


def table(headers: list[str], rows: list[list[str]]) -> str:
    """Render a padded text table."""
    if not rows:
        return dim("(none)")
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], _visible_len(cell))
    out = ["  ".join(_pad(h, widths[i]) for i, h in enumerate(headers)).rstrip()]
    out.append(dim("  ".join("-" * w for w in widths)))
    for row in rows:
        out.append("  ".join(_pad(c, widths[i]) for i, c in enumerate(row)).rstrip())
    return "\n".join(out)


def _visible_len(text: str) -> int:
    """Length ignoring ANSI escapes."""
    out, i = 0, 0
    while i < len(text):
        if text[i] == "\033":
            j = text.find("m", i)
            if j == -1:
                break
            i = j + 1
        else:
            out += 1
            i += 1
    return out


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - _visible_len(text))


def pick(options: list[str], title: str) -> str | None:
    """Numbered picker. Returns the chosen option, or None on blank/EOF."""
    if not options:
        return None
    print(bold(title))
    for i, opt in enumerate(options, 1):
        print(f"  {i}) {opt}")
    try:
        raw = input(bold("> ")).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    if not raw:
        return None
    if raw.isdigit() and 1 <= int(raw) <= len(options):
        return options[int(raw) - 1]
    if raw in options:
        return raw
    return None


def ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


def ok(msg: str) -> None:
    print(f"{green(CHECK)} {msg}")


def fail(msg: str) -> None:
    print(f"{red(CROSS)} {msg}", file=sys.stderr)


def info(msg: str) -> None:
    print(f"{dim(DOT)} {msg}")


def warn(msg: str) -> None:
    print(f"{yellow(WARN)} {msg}")
