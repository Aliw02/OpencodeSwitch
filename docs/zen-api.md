# Zen API — what we measured

Everything below was established by probing `https://opencode.ai/zen/v1` directly
on 2026-09-27 while building `ops`. It is not documented anywhere upstream.

## 1. `GET /models` does not authenticate

The endpoint answers `200` and returns the full model list as long as the
request carries a custom `User-Agent` — **even with no `Authorization` header
at all**.

| Request | Response |
|---|---|
| no auth header, no User-Agent | `403 Forbidden` |
| `Authorization: Bearer <garbage>`, no User-Agent | `403 Forbidden` |
| `Authorization: Bearer <garbage>`, `User-Agent: ops/0.1` | `200`, 82 models |
| **no** auth header, `User-Agent: ops/0.1` | `200`, 82 models |

So `GET /models` cannot be used to validate a key. An early version of `ops`
did exactly that and happily accepted `dummy-key-aaa` as a real credential.

## 2. The probe that actually authenticates

`POST /zen/v1/chat/completions` with an **empty `messages` array**:

```json
{"model": "<free model id>", "messages": [], "max_tokens": 1}
```

Two properties make this the right probe:

- **authentication runs before the free-tier check**, so a bad key never gets
  past step one;
- `messages: []` never reaches generation, so **nothing is billed**.

A real model id must be sent — omitting `model` yields `ModelError` (which also
uses HTTP 401) before anything can be learned about the key.

## 3. Response taxonomy

Send `Authorization: Bearer <key>` plus the probe above:

| Response | Meaning | `ops` verdict |
|---|---|---|
| `401 {"error":{"type":"AuthError","message":"Invalid API key."}}` | key is not real | `invalid` → refuse to save |
| `401 {"error":{"type":"AuthError","message":"Missing API key."}}` | no key sent | `invalid` |
| `403 {"error":{"type":"FreeTierError","message":"OpenCode's free tier can only be used from within OpenCode"}}` | key authenticated; free tier refuses outside the app | `ok` |
| `403 "Upstream request failed: Model access is disabled"` | key authenticated, account has no access to that model | `no_access` |
| `401 {"error":{"type":"ModelError",...}}` | bad/missing model id, tells you nothing about the key | `unverified` |
| `200` | authenticated and used | `ok` |

**`FreeTierError` is a positive signal.** It is only reached after the key has
passed authentication — an invalid key gets `401 AuthError` first. That is what
lets `ops` prove a key for free.

**HTTP status alone is not enough.** Zen uses `401` for `ModelError` too, so a
naive `status == 401 → invalid` check would reject perfectly good keys. `ops`
classifies on the error `type` inside the body.

## 4. Two families of model

Zen serves 82 models:

- **Free / Zen-native** — `big-pickle`, `mimo-v2.6-flash-free`,
  `deepseek-v4-flash-free`, `space-bunny-free`, `jev-1.13-free`,
  `longcat-2.5-preview-free`, `nemotron-*-free`, …
  External calls get `FreeTierError`; inside the OpenCode client they work
  without spending credit.
- **Frontier / paid** — `claude-*`, `gpt-*`, `gemini-*`, `grok-*`, …
  A key without credit gets `Model access is disabled`.

Probing a frontier model therefore reports `no_access` for an account that is
perfectly healthy on free models. `ops` picks a free model
(`big-pickle`, else any `*-free`, else the first id) for this reason.

## 5. No balance or quota endpoint exists

There is no `/me`, `/account`, `/key`, `/keys`, `/auth`, `/user`, `/whoami`,
`/dashboard/billing/*`, or `/api/usage` — all return `404`. This matches
upstream issue [anomalyco/opencode#18648](https://github.com/anomalyco/opencode/issues/18648).

Consequence: `ops` can tell you *whether* a key authenticates, but it cannot
tell you *how much quota is left*. Rotating accounts has to be reactive —
you find out when a request fails.

## 6. Why sessions survive a switch

OpenCode keeps credentials and conversations apart:

- credentials → `~/.local/share/opencode/auth.json`
- sessions → `~/.local/share/opencode/storage/`

`ops` rewrites only the `opencode` key inside `auth.json`. Every other provider
(`nvidia`, `openai`, `modal`, `inference`, `opencode-go`) and every session
leaves untouched.

Verified end to end: before/after comparison of a live `auth.json` showed all
five pre-existing provider keys byte-identical, with `auth.json.bak` restoring
the file exactly if needed.
