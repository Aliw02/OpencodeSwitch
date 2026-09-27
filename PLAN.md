# PLAN — `ops` (OpenCode Switch)

A tiny terminal CLI to manage **multiple OpenCode Zen accounts** and switch between
them instantly, **without losing your sessions**.

---

## 1. Problem

- OpenCode stores **one API key per provider** in `~/.local/share/opencode/auth.json`.
- When your Zen account hits its monthly limit, work stops.
- There is **no built-in rotation** (open feature request:
  [opencode#11830](https://github.com/anomalyco/opencode/issues/11830)).
- Zen's API **does not expose balance/quota**
  ([opencode#18648](https://github.com/anomalyco/opencode/issues/18648)),
  so we cannot predict the limit — we can only swap keys.

## 2. Key insight (why sessions survive)

OpenCode separates concerns:

| Data            | File                                          | Tied to account? |
|-----------------|-----------------------------------------------|------------------|
| Sessions/messages | `~/.local/share/opencode/storage/`           | **No** — per project |
| Credentials     | `~/.local/share/opencode/auth.json`           | Yes — one per provider |

So swapping `auth.json` → `opencode.key` **never touches conversations**.
You switch accounts and `opencode -c` (continue) picks up exactly where you were.

## 3. Scope

**In scope** — manage Zen keys + swap them in `auth.json`.
**Out of scope** — auto-failover proxy, per-request rotation, OAuth accounts.
(A future `ops watch` could poll and warn; not in v1.)

---

## 4. Commands

```
ops account add <name> [key]      Add an account (prompts for key if omitted), validates it first
ops account list                  Table: name, active marker, masked key, last used  (--json)
ops account remove <name>         Delete an account (refuses to remove the active one)
ops account rename <old> <new>    Rename
ops account import <name>         Pull the key currently in auth.json into a named account

ops switch [name]                 Activate an account. No name → numbered picker
ops switch --account <name>       Same, scriptable form
ops current                       Show which account is active + detect drift
ops rotate                        Round-robin to the next account (the "I hit the limit" button)

ops test [name]                   Authenticate stored keys (zero tokens)
ops doctor                        Environment check: python, opencode, paths, all keys
ops run [--account x] -- <args>   Switch, then exec opencode with your args
ops history                       Last 20 switches from the audit log          (--json)
```

Exit codes: `0` ok · `1` user/config error · `2` network/API error.

---

## 5. Storage

**Accounts** — `~/.config/opencode/zen-accounts.json`, mode `0600`:

```json
{
  "version": 1,
  "active": "aliweyabood",
  "accounts": [
    { "name": "aliweyabood", "key": "oc_sk_...", "created": "...", "last_used": "..." }
  ]
}
```

**OpenCode credentials** — `~/.local/share/opencode/auth.json`:

```json
{ "opencode": { "type": "api", "key": "<active key>" } }
```

Only the `opencode` key is ever touched. Every other provider in that file is
preserved verbatim.

**Audit log** — `~/.config/opencode/zen-history.jsonl` (append-only).

**Backups** — `auth.json.bak` written before *every* mutation.

## 6. Path resolution

Uses the same rules as OpenCode (`xdg-basedir`):

1. `OPENCODE_DATA_DIR` → auth.json location
2. `XDG_DATA_HOME`/`OPENCODE_CONFIG_DIR` overrides if set
3. else `~/.local/share/opencode/` and `~/.config/opencode/`

Windows: `~` = `C:\Users\<you>` (not `%APPDATA%`).

## 7. Safety rules

1. **Never** print a full key — always `oc_sk_…ABCD` style masking.
2. **Validate before saving** — `ops account add` proves the key with an empty
   completion request. Auth runs before payload validation, and `messages: []`
   never reaches generation, so nothing is billed.
3. **Atomic writes** — write to `.tmp`, then `os.replace`.
4. **Backup first** — `auth.json.bak` before any change; `ops doctor` offers restore.
5. **Refuse** to remove/rename the active account without `--force`.
6. No network calls except Zen's `/models` (list) and `/chat/completions`
   (auth probe with zero tokens).

## 8. Project structure

```
OpencodeSwitch/
├── PLAN.md              ← this file
├── README.md            ← install + usage
├── pyproject.toml       ← package metadata, `ops` console entry point
├── .gitignore
├── ops/
│   ├── __init__.py      version
│   ├── __main__.py      python -m ops
│   ├── cli.py           argparse wiring + dispatch  (only wiring, no logic)
│   ├── paths.py         resolve opencode config/data dirs, accounts file
│   ├── store.py         load/save accounts, active pointer, history log
│   ├── opencode.py      read/write auth.json safely (+ backup)
│   ├── zen.py           Zen API: validate key, list models
│   ├── ui.py            colors, tables, prompts, key masking
│   ├── account.py       account add/list/remove/rename/import
│   ├── switch.py        switch/current/rotate
│   └── tools.py         test/doctor/run/history
└── tests/
    └── test_store.py    store + auth.json round-trip, no network
```

**Design rule:** `cli.py` only parses and dispatches. All logic lives in the
module that owns the data. No module imports `cli`.

## 9. Dependencies

**None** — Python 3.10+ stdlib only (`argparse`, `json`, `urllib`, `pathlib`,
`getpass`, `os`, `tempfile`, `shutil`, `datetime`).

Install as a global command:

```powershell
pipx install -e .          # or: pip install -e .
ops doctor
```

## 10. Implementation order

1. `paths.py` — resolve the three file locations, fail loudly if opencode absent
2. `store.py` — accounts CRUD + atomic write + history append
3. `opencode.py` — read/write `auth.json` preserving all other providers + backup
4. `zen.py` — `check()` proves a key with `POST /zen/v1/chat/completions`
   (`messages: []`, zero tokens). `/models` does **not** authenticate: it
   answers 200 for any request with a custom User-Agent, even unauthenticated.
5. `ui.py` — table renderer, masked key, colored status, numbered picker
6. `account.py` → `switch.py` → `tools.py`
7. `cli.py` + `__main__.py` — wire subcommands
8. `tests/test_store.py` — round-trip with a temp dir
9. `README.md`, `pip install -e .`, `ops doctor`
10. Commit → push to private repo

## 11. Acceptance

- [ ] `ops account add aliweyabood <key>` validates and stores the key
- [ ] `ops account list` shows both accounts with `*` on the active one
- [ ] `ops switch --account aliweyabood` rewrites only `auth.json.opencode.key`
- [ ] `auth.json` diff shows **no** other provider changed
- [ ] Starting `opencode -c` in a project resumes the same session on the new account
- [ ] `ops rotate` round-robins correctly
- [ ] `ops doctor` reports green on this machine
- [ ] `ops` works from any directory
