from __future__ import annotations

from redis.asyncio import Redis


class RedisTokenBlacklist:
    """Redis implementation of TokenBlacklist protocol."""

    _PREFIX = "blacklist:"

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def blacklist(self, token: str, expires_in: int) -> None:
        key = f"{self._PREFIX}{token}"
        await self._redis.setex(key, expires_in, "1")

    async def is_blacklisted(self, token: str) -> bool:
        key = f"{self._PREFIX}{token}"
        result = await self._redis.get(key)
        return result is not None
