"""zen.check classification - fully offline, _request is stubbed."""

from __future__ import annotations

import pytest

from ops import zen


@pytest.fixture(autouse=True)
def _stub_models(monkeypatch: pytest.MonkeyPatch) -> None:
    # Avoid the /models network call in every test.
    monkeypatch.setattr(zen, "_MODEL_IDS", ["big-pickle", "claude-fable-5"])


def _fake(status: int, body: str):
    def _request(url, **kwargs):
        return status, body

    return _request


def test_auth_error_is_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(zen, "_request", _fake(401, '{"type":"error","error":{"type":"AuthError","message":"Invalid API key."}}'))
    assert zen.check("oc_sk_x").status == "invalid"


def test_missing_key_is_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(zen, "_request", _fake(401, '{"type":"error","error":{"type":"AuthError","message":"Missing API key."}}'))
    assert zen.check("").status == "invalid"


def test_model_error_is_not_treated_as_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zen also uses HTTP 401 for ModelError - must not reject a good key."""
    monkeypatch.setattr(zen, "_request", _fake(401, '{"type":"error","error":{"type":"ModelError","message":"Model x is not supported"}}'))
    assert zen.check("oc_sk_x").status == "unverified"


def test_free_tier_error_means_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zen answers FreeTierError only *after* authenticating the key."""
    monkeypatch.setattr(zen, "_request", _fake(
        403,
        '{"type":"error","error":{"type":"FreeTierError","message":"OpenCode\'s free tier can only be used from within OpenCode"}}',
    ))
    result = zen.check("oc_sk_x")
    assert result.status == "ok"
    assert result.authenticates


def test_no_access_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(zen, "_request", _fake(403, '{"error":{"message":"Upstream request failed: Model access is disabled"}}'))
    result = zen.check("oc_sk_x")
    assert result.status == "no_access"
    assert result.authenticates


def test_ok_when_200(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(zen, "_request", _fake(200, '{"choices":[]}'))
    assert zen.check("oc_sk_x").status == "ok"


def test_other_status_is_unverified_not_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(zen, "_request", _fake(500, '{"error":"boom"}'))
    result = zen.check("oc_sk_x")
    assert result.status == "unverified"
    assert result.authenticates


def test_network_failure_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unreachable Zen must surface as ZenError so the CLI exits 2."""
    def _boom(url, **kwargs):
        raise zen.ZenError("cannot reach Zen: timed out")

    monkeypatch.setattr(zen, "_request", _boom)
    with pytest.raises(zen.ZenError):
        zen.check("oc_sk_x")


def test_model_listing_failure_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(url, **kwargs):
        raise zen.ZenError("Zen returned HTTP 503 for /models")

    monkeypatch.setattr(zen, "_request", _boom)
    monkeypatch.setattr(zen, "_MODEL_IDS", [])
    with pytest.raises(zen.ZenError):
        zen.check("oc_sk_x")


def test_probe_prefers_free_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Free models reject external use after auth, so they prove the key."""
    assert zen._pick_model(["claude-opus-5", "big-pickle"]) == "big-pickle"
    assert zen._pick_model(["claude-opus-5", "mimo-v2.5-free"]) == "mimo-v2.5-free"
    # falls back to the first id rather than failing
    assert zen._pick_model(["claude-opus-5"]) == "claude-opus-5"


def test_probe_sends_chosen_model(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def _capture(url, **kwargs):
        seen.update(kwargs)
        return 403, '{"type":"error","error":{"type":"FreeTierError"}}'

    monkeypatch.setattr(zen, "_request", _capture)
    zen.check("oc_sk_x")
    assert seen["body"]["model"] == "big-pickle"


def test_probe_payload_never_generates(monkeypatch: pytest.MonkeyPatch) -> None:
    """The auth probe must send messages: [] so no tokens can be billed."""
    seen = {}

    def _capture(url, **kwargs):
        seen.update(kwargs)
        return 401, '{"error":{"type":"AuthError"}}'

    monkeypatch.setattr(zen, "_request", _capture)
    zen.check("oc_sk_x")
    assert seen["body"]["messages"] == []
    assert seen["body"]["max_tokens"] == 1
    assert seen["key"] == "oc_sk_x"
