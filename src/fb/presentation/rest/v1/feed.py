from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Response

from fb.application.post.feed_dtos import GetRankedFeedInput
from fb.application.post.get_feed import GetFeedUseCase
from fb.container import Container
from fb.infrastructure.cache.feed_cache import RedisFeedCache
from fb.infrastructure.repositories.feed_repo import SqlAlchemyFeedRepository
from fb.infrastructure.repositories.friend_repo import SqlAlchemyFriendRepository
from fb.presentation.dependencies import get_container, get_current_user_id
from fb.presentation.rest.response import success_response
from fb.presentation.rest.v1.schemas import FeedPostResponse, FeedResponse

router = APIRouter(tags=["feed"])


@router.get("/feed")
async def get_feed(
    mode: str = "ranked",
    limit: int = 20,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> Response:
    """Get user's feed with optional ranking.

    Query params:
        mode: "ranked" (default) or "chronological"
        limit: number of posts to return (1-50, default 20)
    """
    feed_cache = RedisFeedCache(container.redis)

    # 1. Try cache (only for ranked mode, small limit)
    if mode == "ranked" and limit <= 20:
        cached = await feed_cache.get_ranked_feed(current_user_id, limit=limit)
        if cached:
            feed_resp = FeedResponse(
                posts=[FeedPostResponse(**p) for p in cached],
                total_count=len(cached),
                has_next_page=False,
            )
            return success_response(feed_resp.model_dump())

    # 2. DB fetch
    async with container.session_factory() as session:
        feed_repo = SqlAlchemyFeedRepository(session)
        friend_repo = SqlAlchemyFriendRepository(session)
        use_case = GetFeedUseCase(feed_repo=feed_repo, friend_repo=friend_repo)
        result = await use_case.execute_ranked(
            GetRankedFeedInput(user_id=current_user_id, limit=limit, mode=mode)
        )

    # 3. Store in cache (ranked only)
    if mode == "ranked" and result.posts:
        scored = [
            (
                float(time.time()) + i * 0.001,
                {
                    "id": p.id,
                    "author_id": p.author_id,
                    "content": p.content,
                    "media_urls": p.media_urls,
                    "like_count": p.like_count,
                    "comment_count": p.comment_count,
                    "created_at": p.created_at,
                    "score": None,
                },
            )
            for i, p in enumerate(reversed(result.posts))
        ]
        await feed_cache.set_ranked_feed(current_user_id, scored)

    feed_resp = FeedResponse(
        posts=[
            FeedPostResponse(
                id=p.id,
                author_id=p.author_id,
                content=p.content,
                media_urls=p.media_urls,
                like_count=p.like_count,
                comment_count=p.comment_count,
                created_at=p.created_at,
            )
            for p in result.posts
        ],
        total_count=result.total_count,
        has_next_page=result.has_next_page,
    )
    return success_response(feed_resp.model_dump())
