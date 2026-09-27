# ops — OpenCode Switch

[![CI](https://github.com/Aliw02/OpencodeSwitch/actions/workflows/ci.yml/badge.svg)](https://github.com/Aliw02/OpencodeSwitch/actions/workflows/ci.yml)

Switch between multiple **OpenCode Zen** accounts from your terminal, without
losing your sessions.

When one Zen account hits its monthly limit, run `ops rotate` and keep working
in the same conversation.

**Platforms:** Linux, macOS, Windows — Python 3.10+, no third-party
dependencies. CI runs the suite on all three.

## Why sessions survive

OpenCode keeps credentials and conversations in different places:

- credentials → `~/.local/share/opencode/auth.json`
- sessions    → `~/.local/share/opencode/storage/`

`ops` only rewrites the `opencode` key inside `auth.json`. Everything else in
that file (Nvidia, OpenAI, Modal, …) and every session is left untouched.

## Install

```bash
# Linux / macOS
pip install git+https://github.com/Aliw02/OpencodeSwitch.git
# or clone it:
git clone https://github.com/Aliw02/OpencodeSwitch.git
cd OpencodeSwitch && pip install -e .

ops doctor
```

```powershell
# Windows
git clone https://github.com/Aliw02/OpencodeSwitch.git
cd OpencodeSwitch
pip install -e .
ops doctor
```

`ops` lands on your PATH as a normal console script. If it does not, your
`PATH` is missing Python's `Scripts` (Windows) or `bin` (Linux/macOS)
directory.

Paths follow OpenCode's own xdg-basedir resolution on every platform —
`~/.local/share/opencode/` and `~/.config/opencode/` on Linux, macOS and
Windows alike. `OPENCODE_DATA_DIR` / `XDG_DATA_HOME` are honoured the same way
OpenCode honours them.

## Usage

```bash
# 1. add accounts (the key is authenticated against Zen before it is stored,
#    using an empty completion request that spends no tokens)
ops account add aliweyabood oc_sk_xxx
ops account add work                          # prompts for the key, hidden

# 2. see what you have
ops account list

# 3. switch — from any directory
ops switch work
ops switch --account aliweyabood
ops switch                                     # numbered picker

# 4. hit a limit? round-robin to the next account
ops rotate

# then resume where you left off
opencode -c
```

### Every command

| Command | What it does |
|---|---|
| `ops account add <name> [key]` | Add an account, validating the key first |
| `ops account list [--json]` | Table of accounts, `*` marks the active one |
| `ops account remove <name> [--force]` | Delete an account |
| `ops account rename <old> <new>` | Rename |
| `ops account import <name>` | Capture the key currently in `auth.json` |
| `ops switch [name] [--account x]` | Activate an account |
| `ops current [--json]` | Show active account, flags drift |
| `ops rotate` | Round-robin to the next account |
| `ops test [name]` | Probe stored keys against Zen |
| `ops doctor` | Environment + config health check |
| `ops run [--account x] -- <args>` | Switch, then exec opencode |
| `ops history [-n 20] [--json]` | Recent switches |

Exit codes: `0` ok · `1` user/config error · `2` network/API error.

## Files it touches

| File | Purpose |
|---|---|
| `~/.config/opencode/zen-accounts.json` | Your accounts (mode `0600`) |
| `~/.config/opencode/zen-history.jsonl` | Append-only switch log |
| `~/.local/share/opencode/auth.json` | Only the `opencode` key is rewritten |
| `~/.local/share/opencode/auth.json.bak` | Backup taken before every change |

Restore a backup manually:

```bash
cp ~/.local/share/opencode/auth.json.bak ~/.local/share/opencode/auth.json   # Linux / macOS
```
```powershell
Copy-Item ~/.local/share/opencode/auth.json.bak ~/.local/share/opencode/auth.json -Force   # Windows
```

## Safety

- Keys are never printed in full — always `oc_sk_…ABCD`
- Keys are authenticated against Zen before being saved, at zero token cost
- Writes are atomic (temp file + rename)
- `auth.json` is backed up before every mutation
- Refuses to remove the active account without `--force`

## Development

```bash
pip install -e .
pip install pytest
pytest
```

How `ops` proves a Zen key (and why `GET /models` cannot) is written up in
[`docs/zen-api.md`](docs/zen-api.md).
