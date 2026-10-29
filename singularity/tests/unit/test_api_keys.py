"""
Tests for ApiKeyManager (Fáze 7).
"""
import pytest

from core.api_keys import ApiKeyManager


@pytest.fixture()
def manager() -> ApiKeyManager:
    return ApiKeyManager()


def test_create_key_returns_prefixed_string(manager):
    key = manager.create_key("user1")
    assert key.startswith("sk-sg-")
    assert len(key) > len("sk-sg-")


def test_validate_key_returns_user_id(manager):
    key = manager.create_key("alice")
    assert manager.validate_key(key) == "alice"


def test_revoke_key_invalidates_it(manager):
    key = manager.create_key("bob")
    assert manager.revoke_key(key) is True
    assert manager.validate_key(key) is None


def test_revoke_nonexistent_key_returns_false(manager):
    assert manager.revoke_key("sk-sg-nonexistent") is False


def test_list_keys_filters_by_user(manager):
    manager.create_key("carol")
    manager.create_key("carol")
    manager.create_key("dave")
    carol_keys = manager.list_keys(user_id="carol")
    assert len(carol_keys) == 2
    assert all(k["user_id"] == "carol" for k in carol_keys)


def test_delete_user_keys_removes_all(manager):
    manager.create_key("eve")
    manager.create_key("eve")
    count = manager.delete_user_keys("eve")
    assert count == 2
    assert manager.list_keys(user_id="eve") == []


def test_list_keys_masked_prefix(manager):
    key = manager.create_key("frank")
    listing = manager.list_keys(user_id="frank")
    assert len(listing) == 1
    assert "key_prefix" in listing[0]
    assert listing[0]["key_prefix"].endswith("...")
    assert key not in str(listing[0]["key_prefix"])  # raw key not exposed
