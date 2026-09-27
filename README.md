# ops — OpenCode Switch

Switch between multiple **OpenCode Zen** accounts from your terminal, without
losing your sessions.

When one Zen account hits its monthly limit, run `ops rotate` and keep working
in the same conversation.

## Why sessions survive

OpenCode keeps credentials and conversations in different places:

- credentials → `~/.local/share/opencode/auth.json`
- sessions    → `~/.local/share/opencode/storage/`

`ops` only rewrites the `opencode` key inside `auth.json`. Everything else in
that file (Nvidia, OpenAI, Modal, …) and every session is left untouched.

## Install

```powershell
pipx install -e .        # or: pip install -e .
ops doctor
```

Python 3.10+, no third-party dependencies.

## Usage

```powershell
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

```powershell
Copy-Item ~/.local/share/opencode/auth.json.bak ~/.local/share/opencode/auth.json -Force
```

## Safety

- Keys are never printed in full — always `oc_sk_…ABCD`
- Keys are authenticated against Zen before being saved, at zero token cost
- Writes are atomic (temp file + rename)
- `auth.json` is backed up before every mutation
- Refuses to remove the active account without `--force`

## Development

```powershell
pip install -e .[dev]    # or just: pip install pytest
pytest
```

How `ops` proves a Zen key (and why `GET /models` cannot) is written up in
[`docs/zen-api.md`](docs/zen-api.md).
