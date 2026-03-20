"""Prometheus metrics instrumentation for the FastAPI application."""
from __future__ import annotations

# ── METRICS_CARDINALITY_NOTES ─────────────────────────────────────────────────
#
# CARDINALITY RULES (enforced throughout this file):
#   ALLOWED labels  : HTTP method (bounded: GET/POST/PUT/DELETE/PATCH/OPTIONS)
#                     HTTP status_code (bounded: 200/201/204/400/401/403/404/422/500/…)
#                     endpoint path    (bounded: normalised by _normalize_path below)
#                     pool state       (bounded: "checked_out"/"idle"/"overflow")
#                     cache_type       (bounded: "feed"/"profile"/"post"/"friend_count")
#                     operation        (bounded: "select"/"insert"/"update"/"delete")
#   FORBIDDEN labels: user_id, post_id, comment_id, or any unbounded string
#                     that grows proportionally to the data set.
#
# LABEL AUDIT (Phase 4 review, 2026-03-20):
#
#   http_requests_total          [method, endpoint, status_code] ✓ SAFE
#     - endpoint: normalised by _normalize_path(); UUIDs → {id}, numeric IDs → {id}
#     - status_code: HTTP status integers, cardinality ≈ 30
#
#   http_request_duration_seconds [method, endpoint] ✓ SAFE
#     - same normalisation as above
#
#   http_requests_in_progress    [method, endpoint] ✓ SAFE
#
#   websocket_connections_active (no labels) ✓ SAFE
#
#   cache_hits_total             [cache_type] ✓ SAFE
#   cache_misses_total           [cache_type] ✓ SAFE
#     - cache_type is caller-controlled; callers MUST use only the bounded
#       set: "feed", "profile", "post", "friend_count".  Never pass a user ID.
#
#   db_query_duration_seconds    [operation] ✓ SAFE
#     - operation MUST be one of: "select", "insert", "update", "delete".
#       Never include table names or query text.
#
#   feed_cache_hit_ratio         (no labels) ✓ SAFE
#
#   db_pool_checkout_wait_seconds (no labels) ✓ SAFE
#
#   db_pool_connections          [state] ✓ SAFE
#     - state is bounded to: "checked_out", "idle", "overflow"
#
# ─────────────────────────────────────────────────────────────────────────────

import time
from collections.abc import Callable

from fastapi import FastAPI, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# ── Metrics definitions ──────────────────────────────────────────────

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "HTTP requests currently being processed",
    ["method", "endpoint"],
)

WEBSOCKET_CONNECTIONS = Gauge(
    "websocket_connections_active",
    "Active WebSocket connections",
)

CACHE_HITS_TOTAL = Counter(
    "cache_hits_total",
    "Total Redis cache hits",
    ["cache_type"],
)

CACHE_MISSES_TOTAL = Counter(
    "cache_misses_total",
    "Total Redis cache misses",
    ["cache_type"],
)

DB_QUERY_DURATION_SECONDS = Histogram(
    "db_query_duration_seconds",
    "Database query duration",
    ["operation"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
)

FEED_CACHE_HIT_RATIO = Gauge(
    "feed_cache_hit_ratio",
    "Feed cache hit ratio (0-1)",
)

DB_POOL_CHECKOUT_WAIT_SECONDS = Histogram(
    "db_pool_checkout_wait_seconds",
    "Time spent waiting for a connection from the pool (seconds)",
    buckets=[0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
)

DB_POOL_CONNECTIONS = Gauge(
    "db_pool_connections",
    "Current connection pool utilisation",
    ["state"],  # labels: "checked_out", "idle", "overflow"
)

# ── Middleware ────────────────────────────────────────────────────────

def _normalize_path(path: str) -> str:
    """Replace UUIDs and IDs in paths to avoid high cardinality."""
    import re
    # Replace UUID segments
    path = re.sub(
        r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
        '{id}',
        path,
    )
    # Replace numeric IDs
    path = re.sub(r'/\d+', '/{id}', path)
    return path


async def metrics_middleware(request: Request, call_next: Callable) -> Response:
    """ASGI middleware to track HTTP metrics."""
    method = request.method
    endpoint = _normalize_path(request.url.path)

    HTTP_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).inc()
    start = time.perf_counter()

    try:
        response = await call_next(request)
        status = str(response.status_code)
    except Exception:
        status = "500"
        raise
    finally:
        duration = time.perf_counter() - start
        HTTP_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).dec()
        HTTP_REQUESTS_TOTAL.labels(
            method=method, endpoint=endpoint, status_code=status
        ).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(
            method=method, endpoint=endpoint
        ).observe(duration)

    return response


def setup_metrics(app: FastAPI) -> None:
    """Register Prometheus metrics middleware and /metrics endpoint."""
    from starlette.middleware.base import BaseHTTPMiddleware

    app.add_middleware(BaseHTTPMiddleware, dispatch=metrics_middleware)

    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint(request: Request) -> Response:
        """Prometheus scrape endpoint."""
        # Update WebSocket gauge from container
        try:
            container = request.app.state.container
            count = len(container.connection_manager.get_online_users())
            WEBSOCKET_CONNECTIONS.set(count)
        except Exception:
            pass

        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )
