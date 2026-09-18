"""
Singularity — Multi-Tenancy & RBAC (Fáze 65, v2.0 #5).

Adds tenant isolation and role-based access control on top of the single
API-key gate. Every request principal resolves to a (tenant, role); actions
are authorized against a role→permission matrix, so a shared deployment can
serve multiple tenants with admin / user / readonly separation.

  - Role:            ADMIN (everything) > USER (read + write) > READONLY (read)
  - Permission:      coarse action classes (READ, WRITE, ADMIN)
  - TenantRegistry:  tenants, their principals+roles, and API-key → principal
                     resolution; authorize(api_key, permission)

Pure in-memory and dependency-free; pairs with the State Store (Fáze 62) for
shared persistence and the existing API-key auth.
"""

from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass, field
from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    USER = "user"
    READONLY = "readonly"


class Permission(str, Enum):
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


# Which permissions each role grants.
_ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.ADMIN: {Permission.READ, Permission.WRITE, Permission.ADMIN},
    Role.USER: {Permission.READ, Permission.WRITE},
    Role.READONLY: {Permission.READ},
}


def role_can(role: Role, permission: Permission) -> bool:
    return permission in _ROLE_PERMISSIONS.get(role, set())


# ── Data structures ─────────────────────────────────────────────────────────────

@dataclass
class Principal:
    principal_id: str
    tenant_id: str
    role: Role
    api_key: str

    def to_dict(self) -> dict:
        return {
            "principal_id": self.principal_id,
            "tenant_id": self.tenant_id,
            "role": self.role.value,
            # api_key intentionally omitted from listings
        }


@dataclass
class Tenant:
    tenant_id: str
    name: str
    active: bool = True
    principals: dict[str, Principal] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "active": self.active,
            "principals": [p.to_dict() for p in self.principals.values()],
        }


@dataclass
class AuthResult:
    allowed: bool
    reason: str = ""
    tenant_id: str | None = None
    role: str | None = None

    def to_dict(self) -> dict:
        return {"allowed": self.allowed, "reason": self.reason,
                "tenant_id": self.tenant_id, "role": self.role}


# ── Registry ────────────────────────────────────────────────────────────────────

class TenantRegistry:
    """Manage tenants, principals, and API-key based authorization."""

    def __init__(self) -> None:
        self._tenants: dict[str, Tenant] = {}
        self._key_index: dict[str, Principal] = {}   # api_key -> principal
        self._lock = threading.Lock()

        # metrics
        self._authz_checks = 0
        self._authz_denied = 0

    # ── Tenant management ─────────────────────────────────────────────────────────

    def create_tenant(self, tenant_id: str, name: str) -> Tenant:
        if not tenant_id:
            raise ValueError("tenant_id is required")
        with self._lock:
            if tenant_id in self._tenants:
                raise ValueError(f"tenant {tenant_id!r} already exists")
            t = Tenant(tenant_id=tenant_id, name=name)
            self._tenants[tenant_id] = t
            return t

    def delete_tenant(self, tenant_id: str) -> bool:
        with self._lock:
            t = self._tenants.pop(tenant_id, None)
            if t is None:
                return False
            for p in t.principals.values():
                self._key_index.pop(p.api_key, None)
            return True

    def set_active(self, tenant_id: str, active: bool) -> bool:
        with self._lock:
            t = self._tenants.get(tenant_id)
            if t is None:
                return False
            t.active = active
            return True

    def get_tenant(self, tenant_id: str) -> dict | None:
        with self._lock:
            t = self._tenants.get(tenant_id)
            return t.to_dict() if t else None

    def list_tenants(self) -> list[dict]:
        with self._lock:
            return [t.to_dict() for t in self._tenants.values()]

    # ── Principal management ──────────────────────────────────────────────────────

    def add_principal(
        self, tenant_id: str, principal_id: str, role: Role,
        *, api_key: str | None = None,
    ) -> Principal:
        with self._lock:
            t = self._tenants.get(tenant_id)
            if t is None:
                raise KeyError(f"Unknown tenant {tenant_id!r}")
            key = api_key or f"sk_{secrets.token_hex(16)}"
            if key in self._key_index:
                raise ValueError("api_key collision")
            p = Principal(principal_id=principal_id, tenant_id=tenant_id,
                          role=role, api_key=key)
            t.principals[principal_id] = p
            self._key_index[key] = p
            return p

    def remove_principal(self, tenant_id: str, principal_id: str) -> bool:
        with self._lock:
            t = self._tenants.get(tenant_id)
            if t is None:
                return False
            p = t.principals.pop(principal_id, None)
            if p is None:
                return False
            self._key_index.pop(p.api_key, None)
            return True

    def resolve_key(self, api_key: str) -> Principal | None:
        with self._lock:
            return self._key_index.get(api_key)

    # ── Authorization ─────────────────────────────────────────────────────────────

    def authorize(self, api_key: str, permission: Permission) -> AuthResult:
        with self._lock:
            self._authz_checks += 1
            p = self._key_index.get(api_key)
            if p is None:
                self._authz_denied += 1
                return AuthResult(False, "unknown api key")
            t = self._tenants.get(p.tenant_id)
            if t is None or not t.active:
                self._authz_denied += 1
                return AuthResult(False, "tenant inactive", p.tenant_id, p.role.value)
            if not role_can(p.role, permission):
                self._authz_denied += 1
                return AuthResult(False, f"role {p.role.value} lacks {permission.value}",
                                  p.tenant_id, p.role.value)
            return AuthResult(True, "", p.tenant_id, p.role.value)

    # ── Metrics ───────────────────────────────────────────────────────────────────

    def metrics(self) -> dict:
        with self._lock:
            n = self._authz_checks
            return {
                "tenants": len(self._tenants),
                "principals": len(self._key_index),
                "authz_checks": n,
                "authz_denied": self._authz_denied,
                "deny_rate": round(self._authz_denied / n, 4) if n else 0.0,
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._authz_checks = 0
            self._authz_denied = 0
