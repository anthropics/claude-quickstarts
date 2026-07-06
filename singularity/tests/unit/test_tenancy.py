"""
Unit tests — Multi-Tenancy & RBAC (Fáze 65). Fully offline, deterministic.
"""

from __future__ import annotations

import pytest

from core.tenancy import (
    Permission,
    Principal,
    Role,
    Tenant,
    TenantRegistry,
    role_can,
)


# ── Role permission matrix ───────────────────────────────────────────────────────

def test_admin_can_everything():
    for perm in Permission:
        assert role_can(Role.ADMIN, perm)


def test_user_read_write_not_admin():
    assert role_can(Role.USER, Permission.READ)
    assert role_can(Role.USER, Permission.WRITE)
    assert not role_can(Role.USER, Permission.ADMIN)


def test_readonly_read_only():
    assert role_can(Role.READONLY, Permission.READ)
    assert not role_can(Role.READONLY, Permission.WRITE)
    assert not role_can(Role.READONLY, Permission.ADMIN)


# ── Tenant management ────────────────────────────────────────────────────────────

def test_create_tenant():
    r = TenantRegistry()
    t = r.create_tenant("acme", "Acme Corp")
    assert t.tenant_id == "acme"
    assert r.get_tenant("acme")["name"] == "Acme Corp"


def test_create_tenant_requires_id():
    r = TenantRegistry()
    with pytest.raises(ValueError):
        r.create_tenant("", "x")


def test_create_duplicate_tenant_raises():
    r = TenantRegistry()
    r.create_tenant("acme", "Acme")
    with pytest.raises(ValueError):
        r.create_tenant("acme", "Acme2")


def test_list_tenants():
    r = TenantRegistry()
    r.create_tenant("a", "A")
    r.create_tenant("b", "B")
    assert len(r.list_tenants()) == 2


def test_delete_tenant():
    r = TenantRegistry()
    r.create_tenant("acme", "Acme")
    p = r.add_principal("acme", "alice", Role.USER)
    assert r.delete_tenant("acme") is True
    assert r.get_tenant("acme") is None
    # principal's key no longer resolves
    assert r.resolve_key(p.api_key) is None


def test_delete_missing_tenant():
    r = TenantRegistry()
    assert r.delete_tenant("nope") is False


def test_get_missing_tenant_none():
    r = TenantRegistry()
    assert r.get_tenant("nope") is None


# ── Principal management ─────────────────────────────────────────────────────────

def test_add_principal_generates_key():
    r = TenantRegistry()
    r.create_tenant("acme", "Acme")
    p = r.add_principal("acme", "alice", Role.ADMIN)
    assert p.api_key.startswith("sk_")
    assert r.resolve_key(p.api_key).principal_id == "alice"


def test_add_principal_custom_key():
    r = TenantRegistry()
    r.create_tenant("acme", "Acme")
    p = r.add_principal("acme", "bob", Role.USER, api_key="mykey")
    assert p.api_key == "mykey"


def test_add_principal_unknown_tenant_raises():
    r = TenantRegistry()
    with pytest.raises(KeyError):
        r.add_principal("ghost", "x", Role.USER)


def test_add_principal_key_collision_raises():
    r = TenantRegistry()
    r.create_tenant("acme", "Acme")
    r.add_principal("acme", "a", Role.USER, api_key="dup")
    with pytest.raises(ValueError):
        r.add_principal("acme", "b", Role.USER, api_key="dup")


def test_remove_principal():
    r = TenantRegistry()
    r.create_tenant("acme", "Acme")
    p = r.add_principal("acme", "alice", Role.USER)
    assert r.remove_principal("acme", "alice") is True
    assert r.resolve_key(p.api_key) is None


def test_remove_missing_principal():
    r = TenantRegistry()
    r.create_tenant("acme", "Acme")
    assert r.remove_principal("acme", "nobody") is False


def test_principal_dict_omits_api_key():
    r = TenantRegistry()
    r.create_tenant("acme", "Acme")
    r.add_principal("acme", "alice", Role.USER, api_key="secret")
    d = r.get_tenant("acme")["principals"][0]
    assert "api_key" not in d
    assert d["role"] == "user"


# ── Authorization ────────────────────────────────────────────────────────────────

def test_authorize_admin_allowed():
    r = TenantRegistry()
    r.create_tenant("acme", "Acme")
    p = r.add_principal("acme", "alice", Role.ADMIN)
    res = r.authorize(p.api_key, Permission.ADMIN)
    assert res.allowed is True
    assert res.tenant_id == "acme"
    assert res.role == "admin"


def test_authorize_readonly_denied_write():
    r = TenantRegistry()
    r.create_tenant("acme", "Acme")
    p = r.add_principal("acme", "ro", Role.READONLY)
    res = r.authorize(p.api_key, Permission.WRITE)
    assert res.allowed is False
    assert "lacks" in res.reason


def test_authorize_unknown_key():
    r = TenantRegistry()
    res = r.authorize("bogus", Permission.READ)
    assert res.allowed is False
    assert "unknown" in res.reason


def test_authorize_inactive_tenant():
    r = TenantRegistry()
    r.create_tenant("acme", "Acme")
    p = r.add_principal("acme", "alice", Role.ADMIN)
    r.set_active("acme", False)
    res = r.authorize(p.api_key, Permission.READ)
    assert res.allowed is False
    assert "inactive" in res.reason


def test_authorize_result_to_dict():
    r = TenantRegistry()
    r.create_tenant("acme", "Acme")
    p = r.add_principal("acme", "alice", Role.USER)
    d = r.authorize(p.api_key, Permission.READ).to_dict()
    for key in ("allowed", "reason", "tenant_id", "role"):
        assert key in d


def test_tenant_isolation_keys_distinct():
    r = TenantRegistry()
    r.create_tenant("a", "A")
    r.create_tenant("b", "B")
    pa = r.add_principal("a", "alice", Role.USER)
    pb = r.add_principal("b", "bob", Role.USER)
    assert r.authorize(pa.api_key, Permission.READ).tenant_id == "a"
    assert r.authorize(pb.api_key, Permission.READ).tenant_id == "b"


# ── Metrics ──────────────────────────────────────────────────────────────────────

def test_metrics_counts():
    r = TenantRegistry()
    r.create_tenant("acme", "Acme")
    p = r.add_principal("acme", "ro", Role.READONLY)
    r.authorize(p.api_key, Permission.READ)    # allowed
    r.authorize(p.api_key, Permission.WRITE)   # denied
    m = r.metrics()
    assert m["tenants"] == 1
    assert m["principals"] == 1
    assert m["authz_checks"] == 2
    assert m["authz_denied"] == 1
    assert m["deny_rate"] == 0.5


def test_metrics_reset():
    r = TenantRegistry()
    r.create_tenant("acme", "Acme")
    p = r.add_principal("acme", "a", Role.USER)
    r.authorize(p.api_key, Permission.READ)
    r.reset_metrics()
    m = r.metrics()
    assert m["authz_checks"] == 0


def test_metrics_shape():
    r = TenantRegistry()
    m = r.metrics()
    for key in ("tenants", "principals", "authz_checks", "authz_denied", "deny_rate"):
        assert key in m
