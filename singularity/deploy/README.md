# Singularity — Deployment (Fáze 68, v2.0 #8)

Production Kubernetes manifests for the Singularity API.

## Files

| File | Purpose |
|------|---------|
| `k8s/deployment.yaml` | Deployment (2 replicas) with liveness/readiness probes + resource limits |
| `k8s/service.yaml` | ClusterIP Service on port 80 → container port 8001 |
| `k8s/hpa.yaml` | HorizontalPodAutoscaler (CPU 70%, 2–10 replicas) |

## Probes

- **Liveness** → `GET /healthz` — the aggregated subsystem health rollup
  (Fáze 57). Returns **503** when a *required* component is down, so the pod is
  restarted; **200** when healthy or merely degraded.
- **Readiness** → `GET /health/ready` — gates traffic until lifespan startup
  (router → memory → task queue → scheduler) has finished.

## Multi-instance state

The deployment sets `STATE_BACKEND=redis` / `REDIS_URL` so caches, feature
flags, SLO windows and webhook subscriptions are shared across replicas via the
State Store (Fáze 62). Point `REDIS_URL` at your managed Redis.

## Build & apply

```bash
# build the image (from singularity/)
docker build -t singularity:1.0.0 .

# create the API-key secret
kubectl create secret generic singularity-secrets \
  --from-literal=anthropic-api-key="$ANTHROPIC_API_KEY"

# apply
kubectl apply -f deploy/k8s/
```

## Scaling on SLO burn rate

The HPA scales on CPU by default. To scale on the SLO error-budget burn rate
(Fáze 58), expose `/slo` metrics through a Prometheus Adapter and add a
`type: Pods` custom metric to `hpa.yaml`.
