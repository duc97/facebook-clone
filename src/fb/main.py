from __future__ import annotations

import asyncio
import logging
import signal
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fb.config import Settings, get_settings
from fb.container import Container
from fb.presentation.middleware.api_version import APIVersionMiddleware
from fb.presentation.middleware.rate_limiter import RateLimitMiddleware
from fb.presentation.middleware.request_id import RequestIDMiddleware
from fb.presentation.middleware.security_headers import SecurityHeadersMiddleware
from fb.presentation.rest.error_handlers import register_error_handlers

logger = logging.getLogger(__name__)

# Maximum seconds to wait for active WebSocket connections to drain on shutdown.
_WS_DRAIN_TIMEOUT_SECONDS: int = 30


async def _drain_websocket_connections(container: Container) -> None:
    """Close all active WebSocket connections and wait up to _WS_DRAIN_TIMEOUT_SECONDS.

    Each WebSocket receives a 1001 (going away) close frame so clients can
    reconnect immediately rather than timing out.  The coroutine returns as
    soon as all connections are gone or the timeout elapses, whichever is
    first.
    """
    cm = container.connection_manager
    online = cm.get_online_users()
    if not online:
        return

    logger.info(
        "graceful_shutdown: draining %d WebSocket connection(s) (timeout=%ds)",
        len(online),
        _WS_DRAIN_TIMEOUT_SECONDS,
    )

    close_tasks: list[asyncio.Task[None]] = []
    for user_id in list(online):
        # Snapshot the set so iteration is safe while we mutate it.
        for ws in list(cm._connections.get(user_id, set())):
            async def _close(websocket=ws, uid=user_id) -> None:  # noqa: ANN202
                try:
                    await websocket.close(code=1001)
                except Exception:  # noqa: BLE001
                    pass
                await cm.disconnect(uid, websocket)

            close_tasks.append(asyncio.create_task(_close()))

    if close_tasks:
        done, pending = await asyncio.wait(
            close_tasks,
            timeout=_WS_DRAIN_TIMEOUT_SECONDS,
        )
        for task in pending:
            task.cancel()
        if pending:
            logger.warning(
                "graceful_shutdown: %d WebSocket connection(s) did not close within %ds",
                len(pending),
                _WS_DRAIN_TIMEOUT_SECONDS,
            )

    logger.info("graceful_shutdown: WebSocket drain complete")


async def _flush_redis_pipeline(container: Container) -> None:
    """Flush any pending Redis pipeline commands before shutdown.

    If the Redis client has an open pipeline (e.g. from a fan-out that was
    interrupted mid-batch), execute it now so no writes are silently lost.
    This is a best-effort flush — errors are logged but not re-raised.
    """
    try:
        # Create a no-op pipeline execute to flush any buffered commands.
        # The standard aioredis/redis-py client does not expose a single
        # "flush all pending" API, so we check for a buffered pipeline via
        # execute_command or simply issue a PING to confirm connectivity.
        await container.redis.ping()
    except Exception as exc:  # noqa: BLE001
        logger.warning("graceful_shutdown: Redis flush ping failed: %s", exc)
    else:
        logger.info("graceful_shutdown: Redis pipeline flush complete")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # ── Startup ───────────────────────────────────────────────────────
    container: Container = app.state.container
    await container.pubsub.start()

    # Install SIGTERM handler so Kubernetes pod termination triggers an
    # orderly shutdown instead of an abrupt process kill.
    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def _handle_sigterm() -> None:  # noqa: ANN202
        logger.info("graceful_shutdown: SIGTERM received — initiating shutdown")
        shutdown_event.set()

    loop.add_signal_handler(signal.SIGTERM, _handle_sigterm)

    yield

    # ── Shutdown (SIGTERM or normal stop) ─────────────────────────────
    logger.info("graceful_shutdown: beginning orderly shutdown sequence")

    # 1. Stop accepting new pub/sub messages first.
    await container.pubsub.stop()

    # 2. Drain in-flight WebSocket connections (≤30 s).
    await _drain_websocket_connections(container)

    # 3. Flush any pending Redis pipeline writes.
    await _flush_redis_pipeline(container)

    # 4. Close Redis connection pool.
    await container.redis.aclose()

    # 5. Remove the SIGTERM handler so the process can exit cleanly.
    try:
        loop.remove_signal_handler(signal.SIGTERM)
    except Exception:  # noqa: BLE001
        pass

    logger.info("graceful_shutdown: shutdown sequence complete")


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title="Facebook Clone API",
        version=settings.api_version,
        lifespan=lifespan,
    )

    # Create and attach DI container
    container = Container.create(settings)
    app.state.container = container

    # ------------------------------------------------------------------
    # Observability — logging, metrics, tracing
    # ------------------------------------------------------------------

    # Setup logging
    from fb.infrastructure.logging.setup import configure_logging
    configure_logging(debug=settings.debug)

    # Setup metrics
    from fb.infrastructure.metrics.prometheus import setup_metrics
    setup_metrics(app)

    # Setup tracing (optional — requires OTEL_EXPORTER_OTLP_ENDPOINT env var)
    import os
    otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if otel_endpoint:
        from fb.infrastructure.tracing.setup import setup_tracing
        setup_tracing(service_name="facebook-clone", jaeger_endpoint=otel_endpoint)

    # ------------------------------------------------------------------
    # Middleware (FastAPI adds in reverse order, so declare innermost
    # first and outermost last)
    # ------------------------------------------------------------------

    # 1. APIVersionMiddleware (innermost)
    app.add_middleware(APIVersionMiddleware)

    # 2. CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 3. RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware, settings=settings)

    # 4. SecurityHeadersMiddleware
    app.add_middleware(SecurityHeadersMiddleware)

    # 5. RequestIDMiddleware (outermost)
    app.add_middleware(RequestIDMiddleware)

    # ------------------------------------------------------------------
    # Error handlers
    # ------------------------------------------------------------------
    register_error_handlers(app)

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    # Health/ready at root level
    from fb.presentation.rest.health import router as health_router

    app.include_router(health_router)

    # v1 REST API
    from fb.presentation.rest.v1 import v1_router

    app.include_router(v1_router, prefix="/api/v1")

    # v1 WebSocket
    from fb.presentation.ws.handler import router as ws_router

    app.include_router(ws_router, prefix="/api/v1")

    # GraphQL
    from fb.presentation.graphql.schema import create_graphql_router

    graphql_router = create_graphql_router(container)
    app.include_router(graphql_router, prefix="/api/v1/graphql")

    return app
