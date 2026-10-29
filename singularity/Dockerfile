# ── Build stage ───────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

COPY pyproject.toml .
# Install build backend first so hatch resolves deps in one pass
RUN pip install --no-cache-dir hatchling && \
    pip install --no-cache-dir -e "." 2>/dev/null || true

COPY . .
RUN pip install --no-cache-dir -e .

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

RUN useradd --create-home --shell /bin/bash --uid 1001 singularity

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /build /app

RUN mkdir -p /app/data && chown -R singularity:singularity /app

USER singularity

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c \
        "import urllib.request; urllib.request.urlopen('http://localhost:8001/health/live')" \
        || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8001", \
     "--workers", "1", "--log-level", "info"]
