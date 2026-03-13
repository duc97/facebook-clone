# syntax=docker/dockerfile:1.7
# ──────────────────────────────────────────────────────────────────────────────
# Stage 1: base — shared OS setup
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
# Stage 4: production — minimal, non-root, hardened
# ──────────────────────────────────────────────────────────────────────────────
FROM base AS production

# Create non-root user before copying anything
RUN groupadd --gid 1001 app && \
    useradd --uid 1001 --gid app --shell /sbin/nologin --no-create-home app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

WORKDIR /app

# Copy only what runtime needs (not tests, not docs)
COPY --chown=app:app src/ src/
COPY --chown=app:app migrations/ migrations/
COPY --chown=app:app alembic.ini alembic.ini

# Create uploads dir (for local storage backend)
RUN mkdir -p uploads && chown app:app uploads

USER app

EXPOSE 8000

# HEALTHCHECK using curl to /health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Use exec form for proper signal handling
CMD ["uvicorn", "fb.main:create_app", \
     "--factory", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--access-log", \
     "--log-level", "info", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
