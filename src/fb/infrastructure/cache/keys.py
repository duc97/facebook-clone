"""Centralized Redis cache key builders.

Naming convention: ``<domain>:<entity>:<id>[:<variant>]``

TTLs (seconds):
  profile        300   (5 min) — changes infrequently
  post           120   (2 min) — like/comment counts change
  user_posts     60    (1 min) — new posts push feeds
  friends_list   600   (10 min) — friend graph is stable
  notif_unread   30    (30 sec) — real-time feel
  feed           60    (1 min)  — managed by FeedCache separately
"""
from __future__ import annotations

# ── TTL Constants ──────────────────────────────────────────────────────
TTL_PROFILE         = 300   # 5 min
TTL_POST            = 120   # 2 min
TTL_USER_POSTS      = 60    # 1 min
TTL_FRIENDS_LIST    = 600   # 10 min
TTL_FRIEND_COUNT    = 120   # 2 min — invalidated on friend add/remove
TTL_NOTIF_UNREAD    = 30    # 30 sec
TTL_FEED            = 60    # 1 min (feed post ID list)
TTL_MEDIA_LIST      = 120   # 2 min


# ── Key Builders ───────────────────────────────────────────────────────

def profile_key(user_id: str) -> str:
    return f"profile:{user_id}"

def post_key(post_id: str) -> str:
    return f"post:{post_id}"

def user_posts_key(user_id: str, limit: int, offset: int) -> str:
    return f"user_posts:{user_id}:{limit}:{offset}"

def friends_list_key(user_id: str) -> str:
    return f"friends:{user_id}"

def friend_count_key(user_id: str) -> str:
    """Key for the total friend count (integer).  TTL: TTL_FRIEND_COUNT."""
    return f"friend_count:{user_id}"

def notif_unread_key(user_id: str) -> str:
    return f"notif_unread:{user_id}"

def media_list_key(entity_type: str, entity_id: str) -> str:
    return f"media:{entity_type}:{entity_id}"

def post_pattern(post_id: str) -> str:
    """Pattern for all keys related to a post (invalidation)."""
    return f"post:{post_id}*"

def user_pattern(user_id: str) -> str:
    """Pattern for all keys related to a user (invalidation)."""
    return f"*:{user_id}*"
