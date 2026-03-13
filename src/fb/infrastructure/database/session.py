from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from fb.config import Settings


def create_engine(settings: Settings):
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
