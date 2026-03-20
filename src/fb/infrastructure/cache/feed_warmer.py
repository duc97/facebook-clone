"""Feed pre-warming: push new posts into followers' cached feeds."""
from __future__ import annotations

import logging
import time

from redis.asyncio import Redis

from fb.infrastructure.cache.feed_cache import RedisFeedCache

logger = logging.getLogger(__name__)

MAX_FAN_OUT_FRIENDS = 500  # Don't fan-out to >500 friends (celebrities handled differently)


async def fan_out_new_post(
    redis: Redis,
    post_data: dict,
    friend_ids: list[str],
    author_id: str,
) -> None:
    """Push a new post to all friends' cached ranked feeds.

    Fan-out is capped at MAX_FAN_OUT_FRIENDS to avoid thundering-herd.
    For users with more friends, feeds are rebuilt from DB on next request.
    """
    feed_cache = RedisFeedCache(redis)
    score = float(time.time())

    # Always push to author's own feed
    targets = [author_id]
    if len(friend_ids) <= MAX_FAN_OUT_FRIENDS:
        targets.extend(friend_ids)
    else:
        logger.info(
            "Skipping fan-out for author=%s (friend_count=%d > %d)",
            author_id, len(friend_ids), MAX_FAN_OUT_FRIENDS,
        )

    # Batch all ZADD+trim ops into a single pipeline (1 RTT instead of N)
    await feed_cache.batch_prepend_to_feeds(targets, post_data, score=score)


async def invalidate_post_everywhere(redis: Redis, post_id: str) -> None:
    """Remove a deleted/edited post from all feed caches."""
    feed_cache = RedisFeedCache(redis)
    await feed_cache.remove_post_from_feeds(post_id)
    await feed_cache.invalidate_post_payload(post_id)
