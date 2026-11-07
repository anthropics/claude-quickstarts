"""
Multi-Tenancy & RBAC endpoints (Fáze 65, v2.0 #5). Extracted from api/main.py.

Routes and behaviour are identical to the originals.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.state import tenants
from core.tenancy import Permission, Role

router = APIRouter(tags=["Tenancy"])


class TenantCreateRequest(BaseModel):
    tenant_id: str
    name: str


class PrincipalCreateRequest(BaseModel):
    principal_id: str
    role: str            # admin | user | readonly
    api_key: str | None = None


class AuthorizeRequest(BaseModel):
    api_key: str
    permission: str      # read | write | admin


@router.post("/tenants")
async def tenants_create(req: TenantCreateRequest):
    """Create a tenant."""
    try:
        return tenants.create_tenant(req.tenant_id, req.name).to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/tenants")
async def tenants_list():
    """List tenants (principals shown without API keys)."""
    return {"tenants": tenants.list_tenants()}


@router.post("/tenants/{tenant_id}/principals")
async def tenants_add_principal(tenant_id: str, req: PrincipalCreateRequest):
    """Add a principal to a tenant; returns the (one-time) API key."""
    try:
        role = Role(req.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"invalid role {req.role!r}")
    try:
        p = tenants.add_principal(tenant_id, req.principal_id, role, api_key=req.api_key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"principal_id": p.principal_id, "tenant_id": p.tenant_id,
            "role": p.role.value, "api_key": p.api_key}


@router.post("/tenants/authorize")
async def tenants_authorize(req: AuthorizeRequest):
    """Authorize an API key against a permission (read/write/admin)."""
    try:
        perm = Permission(req.permission)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"invalid permission {req.permission!r}")
    return tenants.authorize(req.api_key, perm).to_dict()


@router.get("/tenants/metrics")
async def tenants_metrics():
    """Tenancy metrics: tenants, principals, authz deny rate."""
    return tenants.metrics()
