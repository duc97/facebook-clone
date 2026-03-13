"""Health and readiness probes."""
from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)

_START_TIME = time.time()


@router.get("/health")
async def health() -> dict:
    """Liveness probe — returns 200 if the process is alive."""
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - _START_TIME, 2),
    }


@router.get("/ready")
async def ready(request: Request) -> JSONResponse:
    """Readiness probe — checks DB + Redis connectivity."""
    checks: dict[str, str] = {}
    status_code = 200

    # Check DB
    try:
        container = request.app.state.container
        async with container.session_factory() as session:
            await session.execute(__import__("sqlalchemy").text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        logger.warning("Readiness DB check failed: %s", exc)
        checks["database"] = "error"
        status_code = 503

    # Check Redis
    try:
        await container.redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        logger.warning("Readiness Redis check failed: %s", exc)
        checks["redis"] = "error"
        status_code = 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if status_code == 200 else "degraded",
            "checks": checks,
        },
    )


@router.get("/metrics/simple")
async def simple_metrics(request: Request) -> dict:
    """Simple text metrics — online users, uptime (pre-Prometheus)."""
    try:
        container = request.app.state.container
        online_count = len(container.connection_manager.get_online_users())
    except Exception:
        online_count = -1
    return {
        "uptime_seconds": round(time.time() - _START_TIME, 2),
        "online_users": online_count,
    }
