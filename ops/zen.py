"""Zen API - key validation only.

Zen does not expose balance or quota to API keys
(https://github.com/anomalyco/opencode/issues/18648), so the only thing we
can check is "does this key authenticate and how many models does it see".
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from ops import paths


class ZenError(Exception):
    """Network failure or a non-2xx response from Zen."""


def validate_key(key: str, timeout: float = 15.0) -> int:
    """Return the number of models the key can see, or raise ZenError."""
    req = urllib.request.Request(
        paths.ZEN_MODELS_URL,
        headers={
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "User-Agent": "ops/0.1",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise ZenError("key rejected by Zen (401/403)") from exc
        if exc.code == 429:
            raise ZenError("rate limited by Zen (429) - retry shortly") from exc
        raise ZenError(f"Zen returned HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise ZenError(f"cannot reach Zen: {exc.reason}") from exc

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ZenError("Zen returned a non-JSON body") from exc

    data = payload.get("data")
    if not isinstance(data, list):
        raise ZenError("unexpected Zen response shape")
    return len(data)
