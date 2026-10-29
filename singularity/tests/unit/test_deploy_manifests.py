"""
Validation tests — Kubernetes deploy manifests (Fáze 68).

Ensures the shipped manifests parse and stay consistent with the app: probe
paths point at real endpoints, the container port matches the Dockerfile, and
the Service targets the Deployment.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_DEPLOY = Path(__file__).resolve().parents[2] / "deploy" / "k8s"
_CONTAINER_PORT = 8001  # must match Dockerfile EXPOSE / uvicorn --port


def _load(name: str) -> dict:
    return yaml.safe_load((_DEPLOY / name).read_text())


# ── Files present & parseable ────────────────────────────────────────────────────

def test_manifests_exist():
    for f in ("deployment.yaml", "service.yaml", "hpa.yaml"):
        assert (_DEPLOY / f).exists()


def test_manifests_parse():
    for f in ("deployment.yaml", "service.yaml", "hpa.yaml"):
        doc = _load(f)
        assert isinstance(doc, dict)
        assert "apiVersion" in doc
        assert "kind" in doc


# ── Deployment ───────────────────────────────────────────────────────────────────

def test_deployment_kind():
    assert _load("deployment.yaml")["kind"] == "Deployment"


def test_container_port_matches_dockerfile():
    d = _load("deployment.yaml")
    container = d["spec"]["template"]["spec"]["containers"][0]
    ports = [p["containerPort"] for p in container["ports"]]
    assert _CONTAINER_PORT in ports


def test_liveness_probe_uses_healthz():
    d = _load("deployment.yaml")
    container = d["spec"]["template"]["spec"]["containers"][0]
    assert container["livenessProbe"]["httpGet"]["path"] == "/healthz"


def test_readiness_probe_uses_health_ready():
    d = _load("deployment.yaml")
    container = d["spec"]["template"]["spec"]["containers"][0]
    assert container["readinessProbe"]["httpGet"]["path"] == "/health/ready"


def test_probe_endpoints_exist_in_app():
    # the probe paths must be real routes on the app. Some entries (e.g. mounts
    # from include_router) have no `.path`, so read it defensively.
    from api.main import app
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/healthz" in paths
    assert "/health/ready" in paths


def test_deployment_has_resource_limits():
    d = _load("deployment.yaml")
    container = d["spec"]["template"]["spec"]["containers"][0]
    assert "limits" in container["resources"]
    assert "requests" in container["resources"]


def test_deployment_redis_env_for_shared_state():
    d = _load("deployment.yaml")
    env = {e["name"]: e for e in d["spec"]["template"]["spec"]["containers"][0]["env"]}
    assert env["STATE_BACKEND"]["value"] == "redis"
    assert "REDIS_URL" in env


# ── Service ──────────────────────────────────────────────────────────────────────

def test_service_targets_deployment_selector():
    svc = _load("service.yaml")
    dep = _load("deployment.yaml")
    svc_selector = svc["spec"]["selector"]
    pod_labels = dep["spec"]["template"]["metadata"]["labels"]
    # every service selector label must be present on the pod
    for k, v in svc_selector.items():
        assert pod_labels.get(k) == v


def test_service_targets_named_port():
    svc = _load("service.yaml")
    assert svc["spec"]["ports"][0]["targetPort"] == "http"


# ── HPA ──────────────────────────────────────────────────────────────────────────

def test_hpa_targets_deployment():
    hpa = _load("hpa.yaml")
    ref = hpa["spec"]["scaleTargetRef"]
    assert ref["kind"] == "Deployment"
    assert ref["name"] == "singularity"


def test_hpa_replica_bounds():
    hpa = _load("hpa.yaml")
    assert hpa["spec"]["minReplicas"] >= 1
    assert hpa["spec"]["maxReplicas"] >= hpa["spec"]["minReplicas"]
