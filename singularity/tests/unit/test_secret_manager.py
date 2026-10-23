"""
Tests for SecretManager (Fáze 23).
All offline — no external dependencies.
TTL tests use short durations and time.sleep.
"""
import time
import pytest

from core.secret_manager import SecretManager


@pytest.fixture
def mgr():
    return SecretManager()


def _store(mgr, name="key", value="s3cr3t", owner="alice", **kw):
    return mgr.store(name, value, owner=owner, **kw)


# ── Validation ────────────────────────────────────────────────────────────────

def test_store_empty_name_raises(mgr):
    with pytest.raises(ValueError, match="name"):
        mgr.store("", "val", owner="alice")


def test_store_empty_value_raises(mgr):
    with pytest.raises(ValueError, match="value"):
        mgr.store("k", "", owner="alice")


def test_store_empty_owner_raises(mgr):
    with pytest.raises(ValueError, match="owner"):
        mgr.store("k", "v", owner="")


def test_store_negative_ttl_raises(mgr):
    with pytest.raises(ValueError, match="ttl_s"):
        mgr.store("k", "v", owner="alice", ttl_s=-1.0)


# ── Store & count ─────────────────────────────────────────────────────────────

def test_store_returns_uuid(mgr):
    sid = _store(mgr)
    assert sid is not None and len(sid) == 36


def test_secret_count_all(mgr):
    _store(mgr, owner="alice")
    _store(mgr, owner="bob")
    assert mgr.secret_count() == 2


def test_secret_count_by_owner(mgr):
    _store(mgr, owner="alice")
    _store(mgr, owner="alice")
    _store(mgr, owner="bob")
    assert mgr.secret_count(owner="alice") == 2


# ── Reveal ────────────────────────────────────────────────────────────────────

def test_reveal_returns_value(mgr):
    sid = _store(mgr, value="topsecret", owner="alice")
    assert mgr.reveal(sid, owner="alice") == "topsecret"


def test_reveal_wrong_owner_returns_none(mgr):
    sid = _store(mgr, owner="alice")
    assert mgr.reveal(sid, owner="bob") is None


def test_reveal_missing_returns_none(mgr):
    assert mgr.reveal("ghost", owner="alice") is None


# ── Get (masked) ──────────────────────────────────────────────────────────────

def test_get_masks_value(mgr):
    sid = _store(mgr, value="secret123", owner="alice")
    d = mgr.get(sid, owner="alice")
    assert d["value"] == "***"
    assert d["name"] == "key"


def test_get_wrong_owner_returns_none(mgr):
    sid = _store(mgr, owner="alice")
    assert mgr.get(sid, owner="eve") is None


def test_get_missing_returns_none(mgr):
    assert mgr.get("ghost", owner="alice") is None


# ── List ──────────────────────────────────────────────────────────────────────

def test_list_secrets_by_owner(mgr):
    _store(mgr, name="a", owner="alice")
    _store(mgr, name="b", owner="alice")
    _store(mgr, name="c", owner="bob")
    names = {d["name"] for d in mgr.list_secrets(owner="alice")}
    assert names == {"a", "b"}


def test_list_secrets_by_tag(mgr):
    _store(mgr, name="x", owner="alice", tags=["prod"])
    _store(mgr, name="y", owner="alice", tags=["dev"])
    items = mgr.list_secrets(owner="alice", tag="prod")
    assert len(items) == 1
    assert items[0]["name"] == "x"


# ── Delete ────────────────────────────────────────────────────────────────────

def test_delete_secret(mgr):
    sid = _store(mgr, owner="alice")
    assert mgr.delete(sid, owner="alice") is True
    assert mgr.get(sid, owner="alice") is None


def test_delete_wrong_owner_returns_false(mgr):
    sid = _store(mgr, owner="alice")
    assert mgr.delete(sid, owner="eve") is False


def test_delete_missing_returns_false(mgr):
    assert mgr.delete("ghost", owner="alice") is False


# ── Rotate ────────────────────────────────────────────────────────────────────

def test_rotate_updates_value(mgr):
    sid = _store(mgr, value="old", owner="alice")
    assert mgr.rotate(sid, "new", owner="alice") is True
    assert mgr.reveal(sid, owner="alice") == "new"


def test_rotate_wrong_owner_returns_false(mgr):
    sid = _store(mgr, owner="alice")
    assert mgr.rotate(sid, "new", owner="eve") is False


def test_rotate_empty_value_raises(mgr):
    sid = _store(mgr, owner="alice")
    with pytest.raises(ValueError):
        mgr.rotate(sid, "", owner="alice")


# ── TTL / expiry ──────────────────────────────────────────────────────────────

def test_expired_secret_not_revealed(mgr):
    sid = mgr.store("k", "v", owner="alice", ttl_s=0.05)
    time.sleep(0.1)
    assert mgr.reveal(sid, owner="alice") is None


def test_expired_secret_not_listed(mgr):
    mgr.store("k", "v", owner="alice", ttl_s=0.05)
    time.sleep(0.1)
    assert mgr.list_secrets(owner="alice") == []


def test_purge_expired_removes_entries(mgr):
    mgr.store("k1", "v", owner="alice", ttl_s=0.05)
    mgr.store("k2", "v", owner="alice")  # no TTL
    time.sleep(0.1)
    removed = mgr.purge_expired()
    assert removed == 1
    assert mgr.secret_count() == 1
