from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GetFeedInput:
    """Input for getting user's feed."""

    user_id: str
    limit: int = 20
    offset: int = 0


@dataclass(frozen=True, slots=True)
class FeedPostOutput:
    """Output representation of a post in the feed."""

    id: str
    author_id: str
    content: str
    media_urls: list[str]
    like_count: int
    comment_count: int
    created_at: str | None = None


@dataclass(frozen=True, slots=True)
class FeedOutput:
    """Output for user's feed with pagination info."""

    posts: list[FeedPostOutput]
    total_count: int
    has_next_page: bool


@dataclass(frozen=True, slots=True)
class GetFeedCursorInput:
    """Input for getting user's feed with cursor-based pagination."""

    user_id: str
    first: int = 20
    after: str | None = None


@dataclass(frozen=True, slots=True)
class FeedCursorOutput:
    """Output for user's feed with cursor-based pagination info."""

    posts: list[FeedPostOutput]
    page_info: dict
    total_count: int


@dataclass(frozen=True, slots=True)
class GetRankedFeedInput:
    """Input for getting user's ranked feed."""

    user_id: str
    limit: int = 20
    mode: str = "ranked"  # "ranked" or "chronological"