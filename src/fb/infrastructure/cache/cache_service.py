"""High-level cache service for domain objects.

Each method handles serialization/deserialization of domain DTOs.
This lives in Infrastructure (not Domain) because it depends on Redis.
"""
from __future__ import annotations

import logging

from fb.infrastructure.cache.keys import (
    TTL_FRIENDS_LIST,
    TTL_NOTIF_UNREAD,
    TTL_POST,
    TTL_PROFILE,
    TTL_USER_POSTS,
    friends_list_key,
    notif_unread_key,
    post_key,
    profile_key,
    user_posts_key,
)
from fb.infrastructure.cache.redis_cache import RedisCache

logger = logging.getLogger(__name__)


class CacheService:
    """Domain-aware cache operations. Thin wrapper over RedisCache."""

    def __init__(self, cache: RedisCache) -> None:
        self._cache = cache

    # ── Profile ────────────────────────────────────────────────────────

    async def get_profile(self, user_id: str) -> dict | None:
        return await self._cache.get(profile_key(user_id))

    async def set_profile(self, user_id: str, data: dict) -> None:
        await self._cache.set(profile_key(user_id), data, TTL_PROFILE)

    async def invalidate_profile(self, user_id: str) -> None:
        await self._cache.delete(profile_key(user_id))

    # ── Post ───────────────────────────────────────────────────────────

    async def get_post(self, post_id: str) -> dict | None:
        return await self._cache.get(post_key(post_id))

    async def set_post(self, post_id: str, data: dict) -> None:
        await self._cache.set(post_key(post_id), data, TTL_POST)

    async def invalidate_post(self, post_id: str) -> None:
        await self._cache.delete(post_key(post_id))

    # ── User posts list ────────────────────────────────────────────────

    async def get_user_posts(self, user_id: str, limit: int, offset: int) -> list | None:
        return await self._cache.get(user_posts_key(user_id, limit, offset))

    async def set_user_posts(self, user_id: str, limit: int, offset: int, data: list) -> None:
        await self._cache.set(user_posts_key(user_id, limit, offset), data, TTL_USER_POSTS)

    async def invalidate_user_posts(self, user_id: str) -> None:
        """Invalidate all paginated user-posts caches for this user."""
        await self._cache.delete_pattern(f"user_posts:{user_id}:*")

    # ── Friends list ───────────────────────────────────────────────────

    async def get_friends(self, user_id: str) -> list[str] | None:
        return await self._cache.get(friends_list_key(user_id))

    async def set_friends(self, user_id: str, friend_ids: list[str]) -> None:
        await self._cache.set(friends_list_key(user_id), friend_ids, TTL_FRIENDS_LIST)

    async def invalidate_friends(self, user_id: str) -> None:
        await self._cache.delete(friends_list_key(user_id))

    # ── Notification unread count ──────────────────────────────────────

    async def get_notif_unread(self, user_id: str) -> int | None:
        val = await self._cache.get(notif_unread_key(user_id))
        return int(val) if val is not None else None

    async def set_notif_unread(self, user_id: str, count: int) -> None:
        await self._cache.set(notif_unread_key(user_id), count, TTL_NOTIF_UNREAD)

    async def invalidate_notif_unread(self, user_id: str) -> None:
        await self._cache.delete(notif_unread_key(user_id))
