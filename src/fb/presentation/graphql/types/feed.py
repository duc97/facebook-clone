from __future__ import annotations

import strawberry


@strawberry.type
class FeedPostType:
    """GraphQL type for a post in the feed."""

    id: strawberry.ID
    author_id: str
    text: str
    image: str | None = None
    like_count: int
    comment_count: int
    created_at: str | None = None


@strawberry.type
class FeedResponse:
    """GraphQL type for feed response with pagination."""

    posts: list[FeedPostType]
    total_count: int
    has_next_page: bool
    end_cursor: str | None = None
    start_cursor: str | None = None
