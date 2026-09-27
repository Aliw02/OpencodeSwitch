"""Zen API - key validation.

Zen exposes no balance/quota endpoint (anomalyco/opencode#18648) and
`GET /zen/v1/models` does NOT authenticate - it answers 200 for any request
that carries a custom User-Agent, even with no Authorization header at all.

So we validate by POSTing a deliberately empty chat completion to a *free*
model. Two facts make that work:

  * authentication runs before the free-tier check, so a bad key never gets
    past step one;
  * `messages: []` never reaches generation, so nothing is billed.

Observed responses when the request carries `Authorization: Bearer <key>`:

    invalid key     -> 401 {"error":{"type":"AuthError",
                                     "message":"Invalid API key."}}
    valid key       -> 403 {"error":{"type":"FreeTierError",
                                     "message":"...free tier can only be used
                                     from within OpenCode"}}
    paid-only acct  -> 403 "Upstream request failed: Model access is disabled"
    healthy+in-app  -> 200

`FreeTierError` is therefore a positive signal that the key authenticated.
401 alone is not enough to judge by, because Zen also uses it for `ModelError`.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from ops import paths

# Lazy-cached model ids. A real id must be sent: Zen answers `ModelError`
# before it tells us anything about the key.
_MODEL_IDS: list[str] = []

# Preferred probe targets - free models, which reject external use with
# FreeTierError *after* authentication, at zero token cost.
_PREFERRED_MODELS = ("big-pickle",)

_AUTH_MARKERS = ("AuthError", "Invalid API key", "Missing API key", "invalid api key")
_FREE_TIER_MARKER = "FreeTierError"
_NO_ACCESS_MARKER = "Model access is disabled"


class ZenError(Exception):
    """Network failure - the key could not be checked at all."""


@dataclass
class Result:
    """Outcome of a validation attempt."""

    status: str  # "ok" | "no_access" | "invalid" | "unverified"
    detail: str
    models: int | None = None

    @property
    def authenticates(self) -> bool:
        return self.status != "invalid"


def _request(url: str, *, key: str | None = None, body: dict | None = None,
             timeout: float = 20.0) -> tuple[int, str]:
    headers = {"Accept": "application/json", "User-Agent": "ops/0.1"}
    data = None
    if key is not None:
        headers["Authorization"] = f"Bearer {key}"
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except urllib.error.URLError as exc:
        raise ZenError(f"cannot reach Zen: {exc.reason}") from exc
    except TimeoutError as exc:
        raise ZenError(f"Zen timed out after {timeout}s") from exc


def list_models(timeout: float = 20.0) -> list[str]:
    """Model ids Zen serves. Used to pick a model and to show availability."""
    status, body = _request(paths.ZEN_MODELS_URL, timeout=timeout)
    if status != 200:
        raise ZenError(f"Zen returned HTTP {status} for /models")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ZenError("Zen returned a non-JSON body") from exc
    data = payload.get("data")
    if not isinstance(data, list):
        raise ZenError("unexpected Zen response shape")
    return [m["id"] for m in data if isinstance(m, dict) and "id" in m]


def _pick_model(ids: list[str]) -> str:
    """Prefer a free model: it authenticates, then refuses external use with
    FreeTierError - a positive "this key is real" signal at zero cost."""
    for preferred in _PREFERRED_MODELS:
        if preferred in ids:
            return preferred
    for model_id in ids:
        if model_id.endswith("-free"):
            return model_id
    return ids[0]


def _probe_model() -> str:
    if not _MODEL_IDS:
        ids = list_models()
        if not ids:
            raise ZenError("Zen reported no models")
        _MODEL_IDS.extend(ids)
    return _pick_model(_MODEL_IDS)


def check(key: str, timeout: float = 20.0) -> Result:
    """Authenticate `key` without spending any tokens.

    Raises ZenError when Zen cannot be reached at all (exit code 2); returns
    Result("unverified") when Zen answered but the verdict was ambiguous.
    """
    model = _probe_model()

    status, body = _request(
        paths.ZEN_CHAT_URL,
        key=key,
        body={"model": model, "messages": [], "max_tokens": 1},
        timeout=timeout,
    )

    lower = body.lower()
    if any(m.lower() in lower for m in _AUTH_MARKERS):
        return Result("invalid", "Zen rejected this key")
    if _FREE_TIER_MARKER.lower() in lower:
        # Reached only after authentication - a bad key gets 401 first.
        return Result("ok", f"key authenticated (probe: {model})")
    if _NO_ACCESS_MARKER.lower() in lower:
        return Result(
            "no_access",
            "key authenticates but this account has no model access (out of quota?)",
        )
    if status == 200:
        return Result("ok", f"key accepted (probe: {model})")
    return Result("unverified", f"Zen returned HTTP {status} (key was sent)")
