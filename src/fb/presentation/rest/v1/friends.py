from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Response

from fb.application.follow.dtos import FollowInput, UnfollowInput
from fb.application.follow.follow_user import FollowUserUseCase
from fb.application.follow.get_following import GetFollowingUseCase
from fb.application.follow.unfollow_user import UnfollowUserUseCase
from fb.application.post.dtos import GetPostsByAuthorInput
from fb.application.post.get_post import GetPostUseCase
from fb.container import Container
from fb.infrastructure.repositories.follow_repo import SqlAlchemyFollowRepository
from fb.infrastructure.repositories.post_repo import SqlAlchemyPostRepository
from fb.presentation.dependencies import get_container, get_current_user_id
from fb.presentation.rest.response import paginated_response, success_response
from fb.presentation.rest.v1.schemas import (
    FollowListResponse,
    MessageResponse,
    PostResponse,
)

router = APIRouter(tags=["friends"])

_logger = logging.getLogger(__name__)


# ── GET /friends/{user_id} — See follow list ───────────────────────────


@router.get("/friends/{user_id}")
async def get_follow_list(
    user_id: str,
    limit: int = 20,
    offset: int = 0,
    container: Container = Depends(get_container),
):
    """Get the list of users that user_id is following."""
    async with container.session_factory() as session:
        follow_repo = SqlAlchemyFollowRepository(session)
        use_case = GetFollowingUseCase(follow_repo=follow_repo)
        result = await use_case.execute(user_id, limit=limit, offset=offset)

    return success_response(
        FollowListResponse(
            users=result.user_ids,
            total_count=result.total_count,
        ).model_dump(),
    )


# ── POST /friends/{user_id} — Follow ──────────────────────────────────


@router.post("/friends/{user_id}", status_code=201)
async def follow_user(
    user_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
):
    """Follow another user."""
    uow = container.create_uow()
    async with uow:
        follow_repo = SqlAlchemyFollowRepository(uow.session)
        use_case = FollowUserUseCase(follow_repo=follow_repo, uow=uow)
        await use_case.execute(
            FollowInput(
                follower_id=current_user_id,
                following_id=user_id,
            )
        )

    return success_response(
        MessageResponse(message="Followed successfully").model_dump(),
        status_code=201,
    )


# ── DELETE /friends/{user_id} — Unfollow ───────────────────────────────


@router.delete("/friends/{user_id}", status_code=200)
async def unfollow_user(
    user_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
):
    """Unfollow a user."""
    uow = container.create_uow()
    async with uow:
        follow_repo = SqlAlchemyFollowRepository(uow.session)
        use_case = UnfollowUserUseCase(follow_repo=follow_repo, uow=uow)
        await use_case.execute(
            UnfollowInput(
                follower_id=current_user_id,
                following_id=user_id,
            )
        )

    return success_response(
        MessageResponse(message="Unfollowed successfully").model_dump(),
    )


# ── GET /friends/{user_id}/posts — See user's posts ───────────────────


@router.get("/friends/{user_id}/posts")
async def get_user_posts(
    user_id: str,
    limit: int = 20,
    offset: int = 0,
    container: Container = Depends(get_container),
):
    """Get a paginated list of a user's posts."""
    async with container.session_factory() as session:
        post_repo = SqlAlchemyPostRepository(session)
        use_case = GetPostUseCase(post_repo=post_repo)
        posts = await use_case.execute_by_author(
            GetPostsByAuthorInput(
                author_id=user_id,
                limit=limit,
                offset=offset,
            )
        )

    items = [
        PostResponse(
            id=p.id,
            author_id=p.author_id,
            text=p.content,
            image=p.media_urls[0] if p.media_urls else None,
            like_count=p.like_count,
            comment_count=p.comment_count,
            is_published=p.is_published,
            created_at=p.created_at,
        ).model_dump()
        for p in posts
    ]

    page = (offset // limit) + 1 if limit > 0 else 1
    return paginated_response(
        items,
        total=len(items),
        limit=limit,
        page=page,
        has_next=len(items) == limit,
    )
