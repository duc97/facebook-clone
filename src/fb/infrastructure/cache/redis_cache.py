"""Generic key-value Redis cache with JSON serialization and TTL support."""
from __future__ import annotations

import json
import logging
from typing import Any, TypeVar

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RedisCache:
    """Thin wrapper around Redis for typed JSON cache operations.

    Key namespacing: ``<prefix>:<key>``
    All values are stored as JSON strings.
    """

    def __init__(self, redis: Redis, default_ttl: int = 300) -> None:
        self._redis = redis
        self._default_ttl = default_ttl

    # ── Core operations ───────────────────────────────────────────────

    async def get(self, key: str) -> Any | None:
        """Return deserialized value or None on miss."""
        try:
            raw = await self._redis.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            logger.warning("Cache get failed for key=%s", key, exc_info=True)
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Serialize value to JSON and store with TTL."""
        try:
            await self._redis.setex(
                key,
                ttl if ttl is not None else self._default_ttl,
                json.dumps(value, default=str),
            )
        except Exception:
            logger.warning("Cache set failed for key=%s", key, exc_info=True)

    async def delete(self, key: str) -> None:
        """Delete a single key."""
        try:
            await self._redis.delete(key)
        except Exception:
            logger.warning("Cache delete failed for key=%s", key, exc_info=True)

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a glob pattern. Returns count deleted.

        Uses SCAN (non-blocking) instead of KEYS to avoid blocking Redis.
        Deletes in batches for efficiency.
        """
        try:
            deleted = 0
            cursor: int | bytes = 0
            while True:
                cursor, keys = await self._redis.scan(
                    cursor=cursor, match=pattern, count=100
                )
                if keys:
                    deleted += await self._redis.delete(*keys)
                if not cursor:
                    break
            return deleted
        except Exception:
            logger.warning("Cache delete_pattern failed for pattern=%s", pattern, exc_info=True)
            return 0

    async def mget(self, keys: list[str]) -> list[Any | None]:
        """Batch-fetch multiple keys in a single MGET round trip.

        Returns a list in the same order as ``keys``, with ``None`` for
        misses or deserialization errors.  Falls back gracefully to an
        all-None list on Redis errors so callers can warm from DB.
        """
        if not keys:
            return []
        try:
            raws = await self._redis.mget(*keys)
            results: list[Any | None] = []
            for raw in raws:
                if raw is None:
                    results.append(None)
                else:
                    try:
                        results.append(json.loads(raw))
                    except json.JSONDecodeError:
                        results.append(None)
            return results
        except Exception:
            logger.warning("Cache mget failed for keys=%s", keys, exc_info=True)
            return [None] * len(keys)

    async def get_or_set(
        self,
        key: str,
        loader,
        ttl: int | None = None,
    ) -> Any:
        """Cache-aside: return cached value, or call loader(), cache + return it."""
        cached = await self.get(key)
        if cached is not None:
            return cached
        value = await loader()
        if value is not None:
            await self.set(key, value, ttl)
        return value

    async def increment(self, key: str, ttl: int | None = None) -> int:
        """Atomic increment (for counters). Sets TTL if key is new."""
        try:
            count = await self._redis.incr(key)
            if count == 1 and ttl:
                await self._redis.expire(key, ttl)
            return count
        except Exception:
            logger.warning("Cache increment failed for key=%s", key, exc_info=True)
            return 0

    async def decrement(self, key: str) -> int:
        """Atomic decrement (for counters). Never goes below 0."""
        try:
            count = await self._redis.decr(key)
            if count < 0:
                await self._redis.set(key, 0)
                return 0
            return count
        except Exception:
            logger.warning("Cache decrement failed for key=%s", key, exc_info=True)
            return 0
