"""Redis feed cache — stores scored post payloads in a sorted set.

Key layout:
  feed:ranked:{user_id}   → ZSET  score=feed_score, member=json(FeedPostPayload)
  feed:chron:{user_id}    → ZSET  score=unix_timestamp, member=post_id
  feed:post:{post_id}     → STRING  json(FeedPostPayload), TTL=120s (hot post data)

All ZSETs are capped at MAX_FEED_SIZE entries (trim on write).
"""
from __future__ import annotations

import json
import logging
import time

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

MAX_FEED_SIZE = 200        # max entries per user feed in Redis
DEFAULT_TTL   = 300        # 5 min feed TTL
POST_TTL      = 120        # 2 min individual post payload TTL


class RedisFeedCache:
    """Redis-based feed cache for timeline optimization."""

    _PREFIX = "feed:"
    _DEFAULT_TTL = DEFAULT_TTL

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    # ── Legacy list-based API (backward-compatible) ────────────────────

    async def get_feed(self, user_id: str) -> list[str] | None:
        """Return cached post IDs (legacy list format) or None on miss."""
        key = f"{self._PREFIX}{user_id}"
        result = await self._redis.lrange(key, 0, -1)
        return result if result else None

    async def set_feed(
        self, user_id: str, post_ids: list[str], ttl: int | None = None
    ) -> None:
        """Store post IDs as a list (legacy format)."""
        key = f"{self._PREFIX}{user_id}"
        pipe = self._redis.pipeline()
        await pipe.delete(key)
        if post_ids:
            await pipe.rpush(key, *post_ids)
            await pipe.expire(key, ttl or self._DEFAULT_TTL)
        await pipe.execute()

    async def invalidate(self, user_id: str) -> None:
        """Invalidate all feed keys for a user."""
        pipe = self._redis.pipeline()
        await pipe.delete(f"{self._PREFIX}{user_id}")
        await pipe.delete(f"feed:ranked:{user_id}")
        await pipe.delete(f"feed:chron:{user_id}")
        await pipe.execute()

    # ── Rich sorted-set API ────────────────────────────────────────────

    async def get_ranked_feed(
        self, user_id: str, limit: int = 20
    ) -> list[dict] | None:
        """Return top-N scored post payloads. None = cache miss."""
        key = f"feed:ranked:{user_id}"
        try:
            # ZREVRANGE by score, highest first
            raw_items = await self._redis.zrevrange(key, 0, limit - 1)
            if not raw_items:
                return None
            return [json.loads(item) for item in raw_items]
        except Exception:
            logger.warning("get_ranked_feed failed for user=%s", user_id, exc_info=True)
            return None

    async def set_ranked_feed(
        self,
        user_id: str,
        scored_posts: list[tuple[float, dict]],
        ttl: int = DEFAULT_TTL,
    ) -> None:
        """Store a ranked feed as a sorted set.

        Args:
            scored_posts: list of (score, post_dict) tuples — highest score = top of feed
            ttl: expiry in seconds
        """
        if not scored_posts:
            return
        key = f"feed:ranked:{user_id}"
        try:
            pipe = self._redis.pipeline()
            await pipe.delete(key)
            # zadd expects {member: score} mapping
            mapping = {json.dumps(post, default=str): score for score, post in scored_posts}
            await pipe.zadd(key, mapping)
            # Cap at MAX_FEED_SIZE (remove lowest-score entries)
            if len(scored_posts) > MAX_FEED_SIZE:
                await pipe.zremrangebyrank(key, 0, -(MAX_FEED_SIZE + 1))
            await pipe.expire(key, ttl)
            await pipe.execute()
        except Exception:
            logger.warning("set_ranked_feed failed for user=%s", user_id, exc_info=True)

    async def prepend_to_feed(self, user_id: str, post: dict, score: float | None = None) -> None:
        """Add a new post to the top of user's ranked feed (fan-out on write).

        Uses a pipeline to batch ZADD + trim into a single round-trip.
        """
        key = f"feed:ranked:{user_id}"
        try:
            if score is None:
                score = float(time.time())
            member = json.dumps(post, default=str)
            pipe = self._redis.pipeline()
            await pipe.zadd(key, {member: score})
            # Trim to MAX_FEED_SIZE in the same pipeline (keep top entries)
            await pipe.zremrangebyrank(key, 0, -(MAX_FEED_SIZE + 1))
            await pipe.execute()
        except Exception:
            logger.warning("prepend_to_feed failed for user=%s", user_id, exc_info=True)

    async def batch_prepend_to_feeds(
        self, user_ids: list[str], post: dict, score: float | None = None
    ) -> None:
        """Batch fan-out: add a post to multiple users' feeds in a single pipeline.

        Reduces N sequential round-trips to 1 pipelined call.
        """
        if not user_ids:
            return
        try:
            if score is None:
                score = float(time.time())
            member = json.dumps(post, default=str)
            pipe = self._redis.pipeline()
            for user_id in user_ids:
                key = f"feed:ranked:{user_id}"
                await pipe.zadd(key, {member: score})
                await pipe.zremrangebyrank(key, 0, -(MAX_FEED_SIZE + 1))
            await pipe.execute()
        except Exception:
            logger.warning(
                "batch_prepend_to_feeds failed for %d users", len(user_ids), exc_info=True
            )

    async def remove_post_from_feeds(self, post_id: str) -> None:
        """Remove a deleted/updated post from all cached feeds.

        Uses SCAN (non-blocking) instead of KEYS to iterate feed keys.
        For each feed, uses a pipeline to batch ZREM operations.
        """
        try:
            cursor: int | bytes = 0
            while True:
                cursor, keys = await self._redis.scan(
                    cursor=cursor, match="feed:ranked:*", count=100
                )
                if keys:
                    for key in keys:
                        items = await self._redis.zrange(key, 0, -1)
                        to_remove = []
                        for item in items:
                            try:
                                data = json.loads(item)
                                if data.get("id") == post_id:
                                    to_remove.append(item)
                            except Exception:
                                pass
                        if to_remove:
                            await self._redis.zrem(key, *to_remove)
                if not cursor:
                    break
        except Exception:
            logger.warning("remove_post_from_feeds failed for post=%s", post_id, exc_info=True)

    # ── Per-post hot cache ─────────────────────────────────────────────

    async def get_post_payload(self, post_id: str) -> dict | None:
        """Get a cached post payload (used when assembling feed from IDs)."""
        key = f"feed:post:{post_id}"
        try:
            raw = await self._redis.get(key)
            return json.loads(raw) if raw else None
        except Exception:
            return None

    async def set_post_payload(self, post_id: str, data: dict, ttl: int = POST_TTL) -> None:
        """Cache a post payload for quick feed assembly."""
        key = f"feed:post:{post_id}"
        try:
            await self._redis.setex(key, ttl, json.dumps(data, default=str))
        except Exception:
            logger.warning("set_post_payload failed for post=%s", post_id, exc_info=True)

    async def invalidate_post_payload(self, post_id: str) -> None:
        """Remove a post's hot cache entry."""
        await self._redis.delete(f"feed:post:{post_id}")
