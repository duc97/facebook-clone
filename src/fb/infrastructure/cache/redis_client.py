from __future__ import annotations

from redis.asyncio import Redis

from fb.config import Settings


def create_redis_client(settings: Settings) -> Redis:
    return Redis.from_url(
        settings.redis_url,
        decode_responses=True,
    )
