"""Store + auth.json round-trip. No network."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from ops import opencode, paths, store


@pytest.fixture()
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cfg = tmp_path / "config"
    data = tmp_path / "data"
    cfg.mkdir()
    data.mkdir()
    monkeypatch.setenv("OPENCODE_CONFIG_DIR", str(cfg))
    monkeypatch.setenv("OPENCODE_DATA_DIR", str(data))
    return tmp_path


def _write_auth(data: Path, payload: dict) -> None:
    (data / "auth.json").write_text(json.dumps(payload), encoding="utf-8")


def test_paths_honour_env(sandbox: Path) -> None:
    assert paths.accounts_file() == sandbox / "config" / "zen-accounts.json"
    assert paths.auth_file() == sandbox / "data" / "auth.json"


def test_add_save_load_roundtrip(sandbox: Path) -> None:
    st = store.load()
    st.add("aliweyabood", "oc_sk_ALPHA")
    st.add("work", "oc_sk_BETA")
    store.save(st)

    again = store.load()
    assert again.names() == ["aliweyabood", "work"]
    assert again.active == "aliweyabood"
    assert again.get("work").key == "oc_sk_BETA"


def test_duplicate_name_and_key_rejected(sandbox: Path) -> None:
    st = store.load()
    st.add("a", "k1")
    with pytest.raises(store.StoreError):
        st.add("a", "k2")
    with pytest.raises(store.StoreError):
        st.add("b", "k1")
    with pytest.raises(store.StoreError):
        st.add("has space", "k3")


def test_remove_active_requires_force(sandbox: Path) -> None:
    st = store.load()
    st.add("a", "k1")
    st.add("b", "k2")
    with pytest.raises(store.StoreError):
        st.remove("a")
    st.remove("a", force=True)
    assert st.active == "b"


def test_rename_updates_active(sandbox: Path) -> None:
    st = store.load()
    st.add("a", "k1")
    st.rename("a", "z")
    assert st.active == "z"
    assert st.names() == ["z"]


def test_rotate_round_robin(sandbox: Path) -> None:
    st = store.load()
    st.add("a", "k1")
    st.add("b", "k2")
    st.add("c", "k3")
    seen = [st.next_account().name for _ in range(4)]
    assert seen == ["b", "c", "a", "b"]


def test_write_key_preserves_other_providers(sandbox: Path) -> None:
    original = {
        "nvidia": {"type": "api", "key": "nvapi-KEEP"},
        "openai": {"type": "oauth", "refresh": "r", "access": "a", "expires": 1},
        "opencode": {"type": "api", "key": "OLD"},
    }
    _write_auth(sandbox / "data", original)

    backup = opencode.write_key("NEW")
    assert backup.exists()

    after = json.loads(paths.auth_file().read_text(encoding="utf-8"))
    assert after["nvidia"] == original["nvidia"]
    assert after["openai"] == original["openai"]
    assert after["opencode"]["key"] == "NEW"
    assert after["opencode"]["type"] == "api"
    assert opencode.other_providers() == ["nvidia", "openai"]
    assert opencode.current_key() == "NEW"


def test_write_key_creates_entry_when_missing(sandbox: Path) -> None:
    opencode.write_key("FRESH")
    assert opencode.current_key() == "FRESH"


def test_restore_backup(sandbox: Path) -> None:
    _write_auth(sandbox / "data", {"opencode": {"type": "api", "key": "OLD"}})
    opencode.write_key("NEW")
    assert opencode.current_key() == "NEW"
    assert opencode.restore_backup() is True
    assert opencode.current_key() == "OLD"


@pytest.mark.skipif(sys.platform == "win32", reason="NTFS does not enforce POSIX permission bits")
def test_accounts_file_is_not_world_readable(sandbox: Path) -> None:
    st = store.load()
    st.add("a", "k1")
    store.save(st)
    mode = paths.accounts_file().stat().st_mode
    assert mode & 0o077 == 0


def test_history_append_and_read(sandbox: Path) -> None:
    store.append_history("switch", "a")
    store.append_history("rotate", "b", {"from": "a"})
    rows = store.read_history(10)
    assert [r["action"] for r in rows] == ["rotate", "switch"]
    assert rows[0]["from"] == "a"
