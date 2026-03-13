from __future__ import annotations

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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup — container is already attached in create_app
    container: Container = app.state.container
    await container.pubsub.start()
    yield
    # Shutdown — stop pub/sub, then close Redis connection
    await container.pubsub.stop()
    await container.redis.aclose()


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
