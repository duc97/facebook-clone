from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import Pool, QueuePool

from fb.config import Settings


def _register_pool_listeners(engine: AsyncEngine) -> None:
    """Attach SQLAlchemy pool event listeners to emit Prometheus metrics.

    Metrics emitted:
    - db_pool_checkout_wait_seconds: histogram of time waiting for a free
      connection (measured from the moment checkout is requested to when a
      connection is handed to the caller).
    - db_pool_connections{state="checked_out|idle|overflow"}: gauge showing
      current pool utilisation so capacity can be monitored over time.

    Import is deferred to avoid a hard dependency on prometheus_client when
    the metrics endpoint is not configured (e.g. during unit tests).
    """
    try:
        from fb.infrastructure.metrics.prometheus import (
            DB_POOL_CHECKOUT_WAIT_SECONDS,
            DB_POOL_CONNECTIONS,
        )
    except ImportError:
        # prometheus_client not installed — skip listener registration.
        return

    # SQLAlchemy fires pool events on the *sync* pool that backs the async
    # engine.  Access it via engine.sync_engine.pool.
    pool: Pool = engine.sync_engine.pool

    # Track the checkout-request timestamp per connection object so we can
    # measure wait time precisely in the checkout handler.
    _checkout_start: dict[int, float] = {}

    @event.listens_for(pool, "checkout")
    def _on_checkout(
        dbapi_connection: Any,
        connection_record: Any,
        connection_proxy: Any,
    ) -> None:
        conn_id = id(dbapi_connection)
        wait = time.perf_counter() - _checkout_start.pop(conn_id, time.perf_counter())
        DB_POOL_CHECKOUT_WAIT_SECONDS.observe(wait)
        DB_POOL_CONNECTIONS.labels(state="checked_out").inc()
        DB_POOL_CONNECTIONS.labels(state="idle").dec()

    @event.listens_for(pool, "checkin")
    def _on_checkin(
        dbapi_connection: Any,
        connection_record: Any,
    ) -> None:
        DB_POOL_CONNECTIONS.labels(state="checked_out").dec()
        DB_POOL_CONNECTIONS.labels(state="idle").inc()

    @event.listens_for(pool, "connect")
    def _on_connect(
        dbapi_connection: Any,
        connection_record: Any,
    ) -> None:
        # A brand-new connection is created; record the timestamp so the
        # checkout handler can measure wait time including connection setup.
        _checkout_start[id(dbapi_connection)] = time.perf_counter()
        # Count overflow connections (those above pool_size) separately.
        # QueuePool is the default pool type used by SQLAlchemy for asyncpg.
        if isinstance(pool, QueuePool):
            overflow: int = max(0, pool.checkedout() - pool.size())
            DB_POOL_CONNECTIONS.labels(state="overflow").set(overflow)


def create_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.database_url,
        echo=settings.database_echo,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_pool_max_overflow,
        pool_recycle=settings.db_pool_recycle,
        pool_timeout=settings.db_pool_timeout,
        connect_args={
            "server_settings": {
                "application_name": "facebook_clone",
                # Disable JIT for short OLTP queries — JIT compilation overhead
                # exceeds any gain for the typical sub-millisecond statements here.
                "jit": "off",
            },
            # Per-statement timeout: abort queries that exceed 10 seconds to
            # prevent slow queries from exhausting the connection pool.
            "command_timeout": 10,
        },
    )


def create_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    engine = create_engine(settings)
    _register_pool_listeners(engine)
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        yield session
