from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from fb.infrastructure.cache.feed_cache import RedisFeedCache
from fb.infrastructure.cache.token_blacklist import RedisTokenBlacklist


class TestRedisTokenBlacklist:
    async def test_blacklist_calls_setex(self) -> None:
        """blacklist() stores token in Redis with TTL."""
        mock_redis = AsyncMock()
        bl = RedisTokenBlacklist(mock_redis)

        await bl.blacklist("my-token", 900)

        mock_redis.setex.assert_awaited_once_with("blacklist:my-token", 900, "1")

    async def test_is_blacklisted_returns_true(self) -> None:
        """is_blacklisted() returns True when token exists in Redis."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "1"
        bl = RedisTokenBlacklist(mock_redis)

        result = await bl.is_blacklisted("bad-token")

        assert result is True
        mock_redis.get.assert_awaited_once_with("blacklist:bad-token")

    async def test_is_blacklisted_returns_false(self) -> None:
        """is_blacklisted() returns False when token not in Redis."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        bl = RedisTokenBlacklist(mock_redis)

        result = await bl.is_blacklisted("good-token")

        assert result is False


class TestRedisFeedCache:
    async def test_get_feed_returns_list(self) -> None:
        """get_feed() returns list of post IDs from Redis."""
        mock_redis = AsyncMock()
        mock_redis.lrange.return_value = ["post1", "post2", "post3"]
        cache = RedisFeedCache(mock_redis)

        result = await cache.get_feed("user-123")

        assert result == ["post1", "post2", "post3"]
        mock_redis.lrange.assert_awaited_once_with("feed:user-123", 0, -1)

    async def test_get_feed_returns_none_when_empty(self) -> None:
        """get_feed() returns None when no cached feed."""
        mock_redis = AsyncMock()
        mock_redis.lrange.return_value = []
        cache = RedisFeedCache(mock_redis)

        result = await cache.get_feed("user-456")

        assert result is None

    async def test_set_feed_stores_posts(self) -> None:
        """set_feed() stores post IDs in Redis list with TTL."""
        mock_redis = MagicMock()
        mock_pipe = AsyncMock()
        mock_redis.pipeline.return_value = mock_pipe
        cache = RedisFeedCache(mock_redis)

        await cache.set_feed("user-123", ["p1", "p2"])

        mock_pipe.delete.assert_awaited_once_with("feed:user-123")
        mock_pipe.rpush.assert_awaited_once_with("feed:user-123", "p1", "p2")
        mock_pipe.expire.assert_awaited_once_with("feed:user-123", 300)
        mock_pipe.execute.assert_awaited_once()

    async def test_set_feed_with_custom_ttl(self) -> None:
        """set_feed() uses custom TTL when provided."""
        mock_redis = MagicMock()
        mock_pipe = AsyncMock()
        mock_redis.pipeline.return_value = mock_pipe
        cache = RedisFeedCache(mock_redis)

        await cache.set_feed("user-123", ["p1"], ttl=600)

        mock_pipe.expire.assert_awaited_once_with("feed:user-123", 600)

    async def test_set_feed_empty_list(self) -> None:
        """set_feed() with empty list only deletes the key."""
        mock_redis = MagicMock()
        mock_pipe = AsyncMock()
        mock_redis.pipeline.return_value = mock_pipe
        cache = RedisFeedCache(mock_redis)

        await cache.set_feed("user-123", [])

        mock_pipe.delete.assert_awaited_once_with("feed:user-123")
        mock_pipe.rpush.assert_not_awaited()
        mock_pipe.execute.assert_awaited_once()

    async def test_invalidate_deletes_key(self) -> None:
        """invalidate() removes the feed cache key."""
        mock_redis = AsyncMock()
        cache = RedisFeedCache(mock_redis)

        await cache.invalidate("user-123")

        mock_redis.delete.assert_awaited_once_with("feed:user-123")

    def test_default_ttl(self) -> None:
        """Default TTL is 300 seconds (5 minutes)."""
        assert RedisFeedCache._DEFAULT_TTL == 300

    def test_prefix(self) -> None:
        """Feed cache key prefix is 'feed:'."""
        assert RedisFeedCache._PREFIX == "feed:"
