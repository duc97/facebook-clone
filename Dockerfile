# syntax=docker/dockerfile:1.7
# ──────────────────────────────────────────────────────────────────────────────
# Multi-stage build: dev uses python:3.12-slim; prod uses Distroless (~50 MB,
# no shell, no apt, minimal CVE surface). Compatible with Docker and Podman.
# ──────────────────────────────────────────────────────────────────────────────

# Stage 1: base — shared OS setup (also source of runtime .so libs for prod)
# ──────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install minimal OS deps (libpq for asyncpg, curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# ──────────────────────────────────────────────────────────────────────────────
# Stage 2: builder — compile wheels
# ──────────────────────────────────────────────────────────────────────────────
FROM base AS builder

# Install build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy only dependency files first (layer cache: only rebuild when deps change)
COPY pyproject.toml .
COPY src/ src/

# Install into /install prefix for clean copy into runtime stage
RUN pip install --upgrade pip hatchling && \
    pip install --prefix=/install --no-warn-script-location .

# ──────────────────────────────────────────────────────────────────────────────
# Stage 3: development — with dev deps, hot-reload
# ──────────────────────────────────────────────────────────────────────────────
FROM base AS development

COPY --from=builder /install /usr/local

WORKDIR /app

# Install dev extras
RUN pip install pytest pytest-asyncio pytest-cov httpx ruff mypy

# Create non-root user
RUN groupadd --gid 1001 app && \
    useradd --uid 1001 --gid app --shell /bin/bash --create-home app

COPY --chown=app:app . .
RUN mkdir -p uploads && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uvicorn", "fb.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ──────────────────────────────────────────────────────────────────────────────
# Stage 4: production — Distroless, minimal attack surface, non-root (UID 65532)
#
# gcr.io/distroless/python3-debian12:nonroot has:
#   • No shell, no apt, no pip, no curl → ~50 MB vs ~130 MB for python:3.12-slim
#   • Built-in "nonroot" user (UID/GID 65532)
#   • No useradd/groupadd/mkdir → user files must be owned at build time via
#     COPY --chown, and runtime libs must be copied from the base stage
# ──────────────────────────────────────────────────────────────────────────────
FROM gcr.io/distroless/python3-debian12:nonroot AS production

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy PostgreSQL client shared libs from base (asyncpg needs libpq at runtime).
# Distroless ships no apt, so we pull the .so files from the slim base stage.
COPY --from=base /usr/lib/x86_64-linux-gnu/libpq.so.5 /usr/lib/x86_64-linux-gnu/libpq.so.5
COPY --from=base /usr/lib/x86_64-linux-gnu/libssl.so.3 /usr/lib/x86_64-linux-gnu/libssl.so.3
COPY --from=base /usr/lib/x86_64-linux-gnu/libcrypto.so.3 /usr/lib/x86_64-linux-gnu/libcrypto.so.3

# Copy only what runtime needs (not tests, not docs).
# --chown targets the Distroless built-in nonroot user (UID/GID 65532).
COPY --chown=65532:65532 src/ /app/src/
COPY --chown=65532:65532 migrations/ /app/migrations/
COPY --chown=65532:65532 alembic.ini /app/alembic.ini

WORKDIR /app

# NOTE: uploads dir is provided via a volume mount in compose (no mkdir in Distroless)

EXPOSE 8000

# Healthcheck: Python replaces curl — curl is not present in Distroless
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD ["python3", "-c", \
         "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]

# Use exec form for proper signal handling (no shell in Distroless anyway)
CMD ["uvicorn", "fb.main:create_app", \
     "--factory", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--access-log", \
     "--log-level", "info", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
