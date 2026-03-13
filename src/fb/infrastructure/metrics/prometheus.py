"""Prometheus metrics instrumentation for the FastAPI application."""
from __future__ import annotations

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
