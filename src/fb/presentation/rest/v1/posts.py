from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, File, Response, UploadFile

from fb.application.notification.notification_service import NotificationService
from fb.application.post.create_comment import CreateCommentUseCase
from fb.application.post.create_post import CreatePostUseCase
from fb.application.post.delete_comment import DeleteCommentUseCase
from fb.application.post.delete_post import DeletePostUseCase
from fb.application.post.delete_share import DeleteShareUseCase
from fb.application.post.dtos import (
    CreatePostInput as CreatePostDTO,
    DeletePostInput as DeletePostDTO,
    GetPostInput as GetPostDTO,
    UpdatePostInput as UpdatePostDTO,
)
from fb.application.post.get_comments import GetCommentsUseCase
from fb.application.post.get_post import GetPostUseCase
from fb.application.post.interaction_dtos import (
    CreateCommentInput as CreateCommentDTO,
    DeleteCommentInput as DeleteCommentDTO,
    DeleteShareInput as DeleteShareDTO,
    LikePostInput as LikePostDTO,
    ReactToPostInput as ReactToPostDTO,
    RemoveReactionInput as RemoveReactionDTO,
    SharePostInput as SharePostDTO,
    UnlikePostInput as UnlikePostDTO,
)
from fb.application.post.like_post import LikePostUseCase
from fb.application.post.react_post import ReactToPostUseCase
from fb.application.post.remove_reaction import RemoveReactionUseCase
from fb.application.post.share_post import SharePostUseCase
from fb.application.post.unlike_post import UnlikePostUseCase
from fb.application.post.update_post import UpdatePostUseCase
from fb.application.post.upload_media import UploadMediaInput, UploadMediaUseCase
from fb.container import Container
from fb.domain.shared.entity_id import EntityId
from fb.infrastructure.repositories.notification_repo import SqlAlchemyNotificationRepository
from fb.infrastructure.repositories.comment_repo import SqlAlchemyCommentRepository
from fb.infrastructure.repositories.like_repo import SqlAlchemyLikeRepository
from fb.infrastructure.repositories.post_repo import SqlAlchemyPostRepository
from fb.infrastructure.repositories.reaction_repo import SqlAlchemyReactionRepository
from fb.infrastructure.repositories.share_repo import SqlAlchemyShareRepository
from fb.infrastructure.cache.feed_warmer import fan_out_new_post as _fan_out_new_post
from fb.infrastructure.cache.feed_warmer import invalidate_post_everywhere as _invalidate_post_everywhere
from fb.presentation.dependencies import get_container, get_current_user_id
from fb.presentation.rest.response import paginated_response, success_response
from fb.presentation.rest.v1.schemas import (
    CommentCreateRequest,
    CommentResponse,
    LikeResponse,
    MediaUploadResponse,
    PostCreateRequest,
    PostResponse,
    PostUpdateRequest,
    ReactionRequest,
    ReactionResponse,
    ReactionsListResponse,
    ShareRequest,
    ShareResponse,
)

router = APIRouter(tags=["posts"])

_logger = logging.getLogger(__name__)


# ── Background notification helpers ─────────────────────────────────────


async def _notify_like(container: "Container", post_id: str, liker_id: str) -> None:
    """Fire-and-forget: notify post author when someone likes their post."""
    try:
        async with container.session_factory() as session:
            post_repo = SqlAlchemyPostRepository(session)
            post = await post_repo.find_by_id(EntityId.from_str(post_id))
            if post is None:
                return
            post_author_id = str(post.author_id)

        uow = container.create_uow()
        async with uow:
            notif_repo = SqlAlchemyNotificationRepository(uow.session)
            svc = NotificationService(
                notification_repo=notif_repo,
                uow=uow,
                pubsub=container.pubsub,
            )
            await svc.notify_like(
                post_author_id=post_author_id,
                liker_id=liker_id,
                post_id=post_id,
            )
    except Exception:
        _logger.exception("_notify_like failed for post=%s liker=%s", post_id, liker_id)


async def _notify_comment(container: "Container", post_id: str, commenter_id: str) -> None:
    """Fire-and-forget: notify post author when someone comments on their post."""
    try:
        async with container.session_factory() as session:
            post_repo = SqlAlchemyPostRepository(session)
            post = await post_repo.find_by_id(EntityId.from_str(post_id))
            if post is None:
                return
            post_author_id = str(post.author_id)

        uow = container.create_uow()
        async with uow:
            notif_repo = SqlAlchemyNotificationRepository(uow.session)
            svc = NotificationService(
                notification_repo=notif_repo,
                uow=uow,
                pubsub=container.pubsub,
            )
            await svc.notify_comment(
                post_author_id=post_author_id,
                commenter_id=commenter_id,
                post_id=post_id,
            )
    except Exception:
        _logger.exception(
            "_notify_comment failed for post=%s commenter=%s", post_id, commenter_id
        )


async def _notify_reaction(
    container: "Container", post_id: str, reactor_id: str, reaction_type: str
) -> None:
    """Fire-and-forget: notify post author when someone reacts to their post."""
    try:
        async with container.session_factory() as session:
            post_repo = SqlAlchemyPostRepository(session)
            post = await post_repo.find_by_id(EntityId.from_str(post_id))
            if post is None:
                return
            post_author_id = str(post.author_id)

        uow = container.create_uow()
        async with uow:
            notif_repo = SqlAlchemyNotificationRepository(uow.session)
            svc = NotificationService(
                notification_repo=notif_repo,
                uow=uow,
                pubsub=container.pubsub,
            )
            await svc.notify_reaction(
                post_author_id=post_author_id,
                reactor_id=reactor_id,
                post_id=post_id,
                reaction_type=reaction_type,
            )
    except Exception:
        _logger.exception(
            "_notify_reaction failed for post=%s reactor=%s", post_id, reactor_id
        )


async def _notify_share(container: "Container", post_id: str, sharer_id: str) -> None:
    """Fire-and-forget: notify post author when someone shares their post."""
    try:
        async with container.session_factory() as session:
            post_repo = SqlAlchemyPostRepository(session)
            post = await post_repo.find_by_id(EntityId.from_str(post_id))
            if post is None:
                return
            post_author_id = str(post.author_id)

        uow = container.create_uow()
        async with uow:
            notif_repo = SqlAlchemyNotificationRepository(uow.session)
            svc = NotificationService(
                notification_repo=notif_repo,
                uow=uow,
                pubsub=container.pubsub,
            )
            await svc.notify_share(
                post_author_id=post_author_id,
                sharer_id=sharer_id,
                post_id=post_id,
            )
    except Exception:
        _logger.exception("_notify_share failed for post=%s sharer=%s", post_id, sharer_id)


async def _trigger_feed_fan_out(
    container: "Container",
    result: Any,
    author_id: str,
) -> None:
    """Fire-and-forget: fan-out a newly created post to friends' cached feeds."""
    try:
        async with container.session_factory() as session:
            from fb.infrastructure.repositories.friend_repo import SqlAlchemyFriendRepository as _FriendRepo
            from fb.domain.shared.entity_id import EntityId as _EId
            friend_repo = _FriendRepo(session)
            friend_ids_objs = await friend_repo.get_friends(_EId.from_str(author_id), limit=500)
        friend_ids = [str(f) for f in friend_ids_objs]

        post_data = {
            "id": result.id,
            "author_id": result.author_id,
            "content": result.content,
            "media_urls": result.media_urls,
            "like_count": result.like_count,
            "comment_count": result.comment_count,
            "created_at": result.created_at,
            "score": None,
        }
        await _fan_out_new_post(container.redis, post_data, friend_ids, author_id)
    except Exception:
        pass  # best-effort


@router.post("/posts", status_code=201)
async def create_post(
    body: PostCreateRequest,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> Response:
    """Create a new post."""
    uow = container.create_uow()
    async with uow:
        post_repo = SqlAlchemyPostRepository(uow.session)
        use_case = CreatePostUseCase(post_repo=post_repo, uow=uow)
        result = await use_case.execute(
            CreatePostDTO(
                author_id=current_user_id,
                content=body.content,
                media_urls=body.media_urls,
            )
        )

    asyncio.create_task(_trigger_feed_fan_out(container, result, current_user_id))

    return success_response(
        PostResponse(
            id=result.id,
            author_id=result.author_id,
            content=result.content,
            media_urls=result.media_urls,
            like_count=result.like_count,
            comment_count=result.comment_count,
            is_published=result.is_published,
            created_at=result.created_at,
        ).model_dump(),
        status_code=201,
    )


@router.get("/posts/{post_id}")
async def get_post(
    post_id: str,
    container: Container = Depends(get_container),
) -> Response:
    """Get a post by ID."""
    # 1. Cache check — return immediately on hit
    cached = await container.cache.get_post(post_id)
    if cached is not None:
        return success_response(cached)

    # 2. DB fetch (use case raises PostNotFoundError on miss)
    async with container.session_factory() as session:
        post_repo = SqlAlchemyPostRepository(session)
        use_case = GetPostUseCase(post_repo=post_repo)
        result = await use_case.execute(GetPostDTO(post_id=post_id))

    # 3. Serialize, cache, and return
    data = PostResponse(
        id=result.id,
        author_id=result.author_id,
        content=result.content,
        media_urls=result.media_urls,
        like_count=result.like_count,
        comment_count=result.comment_count,
        is_published=result.is_published,
        created_at=result.created_at,
    ).model_dump()
    await container.cache.set_post(post_id, data)
    return success_response(data)


@router.put("/posts/{post_id}")
async def update_post(
    post_id: str,
    body: PostUpdateRequest,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> Response:
    """Update a post. Only the author can update their own post."""
    uow = container.create_uow()
    async with uow:
        post_repo = SqlAlchemyPostRepository(uow.session)
        use_case = UpdatePostUseCase(post_repo=post_repo, uow=uow)
        result = await use_case.execute(
            UpdatePostDTO(
                post_id=post_id,
                user_id=current_user_id,
                content=body.content,
            )
        )

    asyncio.create_task(_invalidate_post_everywhere(container.redis, post_id))
    await container.cache.invalidate_post(post_id)

    return success_response(
        PostResponse(
            id=result.id,
            author_id=result.author_id,
            content=result.content,
            media_urls=result.media_urls,
            like_count=result.like_count,
            comment_count=result.comment_count,
            is_published=result.is_published,
            created_at=result.created_at,
        ).model_dump(),
    )


@router.delete("/posts/{post_id}", status_code=204)
async def delete_post(
    post_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> Response:
    """Delete a post. Only the author can delete their own post."""
    uow = container.create_uow()
    async with uow:
        post_repo = SqlAlchemyPostRepository(uow.session)
        use_case = DeletePostUseCase(post_repo=post_repo, uow=uow)
        await use_case.execute(
            DeletePostDTO(
                post_id=post_id,
                user_id=current_user_id,
            )
        )

    asyncio.create_task(_invalidate_post_everywhere(container.redis, post_id))
    await container.cache.invalidate_post(post_id)

    return Response(status_code=204)


@router.get("/posts/{post_id}/comments")
async def get_comments(
    post_id: str,
    limit: int = 20,
    offset: int = 0,
    container: Container = Depends(get_container),
) -> Response:
    """Get paginated comments for a post."""
    async with container.session_factory() as session:
        comment_repo = SqlAlchemyCommentRepository(session)
        use_case = GetCommentsUseCase(comment_repo=comment_repo)
        result = await use_case.execute(post_id, limit, offset)

    items = [
        CommentResponse(
            id=c.id,
            post_id=c.post_id,
            author_id=c.author_id,
            content=c.content,
            created_at=c.created_at,
        ).model_dump()
        for c in result.comments
    ]

    return paginated_response(
        items,
        total=result.total_count,
        limit=limit,
        has_next=result.has_next_page,
    )


@router.post("/posts/{post_id}/comments", status_code=201)
async def create_comment(
    post_id: str,
    body: CommentCreateRequest,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> Response:
    """Create a comment on a post."""
    uow = container.create_uow()
    async with uow:
        comment_repo = SqlAlchemyCommentRepository(uow.session)
        post_repo = SqlAlchemyPostRepository(uow.session)
        use_case = CreateCommentUseCase(
            comment_repo=comment_repo, post_repo=post_repo, uow=uow
        )
        result = await use_case.execute(
            CreateCommentDTO(
                post_id=post_id,
                author_id=current_user_id,
                content=body.content,
            )
        )

    asyncio.create_task(_notify_comment(container, post_id, current_user_id))

    return success_response(
        CommentResponse(
            id=result.id,
            post_id=result.post_id,
            author_id=result.author_id,
            content=result.content,
            created_at=result.created_at,
        ).model_dump(),
        status_code=201,
    )


@router.delete("/posts/{post_id}/comments/{comment_id}", status_code=204)
async def delete_comment(
    post_id: str,
    comment_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> Response:
    """Delete a comment. Only the comment author can delete it."""
    uow = container.create_uow()
    async with uow:
        comment_repo = SqlAlchemyCommentRepository(uow.session)
        post_repo = SqlAlchemyPostRepository(uow.session)
        use_case = DeleteCommentUseCase(
            comment_repo=comment_repo, post_repo=post_repo, uow=uow
        )
        await use_case.execute(
            DeleteCommentDTO(
                comment_id=comment_id,
                user_id=current_user_id,
            )
        )

    return Response(status_code=204)


@router.post("/posts/{post_id}/like", status_code=201)
async def like_post(
    post_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> Response:
    """Like a post."""
    uow = container.create_uow()
    async with uow:
        like_repo = SqlAlchemyLikeRepository(uow.session)
        post_repo = SqlAlchemyPostRepository(uow.session)
        use_case = LikePostUseCase(
            like_repo=like_repo, post_repo=post_repo, uow=uow
        )
        result = await use_case.execute(
            LikePostDTO(
                post_id=post_id,
                user_id=current_user_id,
            )
        )

    asyncio.create_task(_notify_like(container, post_id, current_user_id))
    await container.cache.invalidate_post(post_id)

    return success_response(
        LikeResponse(
            id=result.id,
            post_id=result.post_id,
            user_id=result.user_id,
        ).model_dump(),
        status_code=201,
    )


@router.delete("/posts/{post_id}/like", status_code=204)
async def unlike_post(
    post_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> Response:
    """Remove a like from a post."""
    uow = container.create_uow()
    async with uow:
        like_repo = SqlAlchemyLikeRepository(uow.session)
        post_repo = SqlAlchemyPostRepository(uow.session)
        use_case = UnlikePostUseCase(
            like_repo=like_repo, post_repo=post_repo, uow=uow
        )
        await use_case.execute(
            UnlikePostDTO(
                post_id=post_id,
                user_id=current_user_id,
            )
        )

    await container.cache.invalidate_post(post_id)

    return Response(status_code=204)


# ── Reaction Endpoints ──────────────────────────────────────────────────


@router.post("/posts/{post_id}/reactions", status_code=201)
async def react_to_post(
    post_id: str,
    body: ReactionRequest,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> Response:
    """Add or update a reaction on a post."""
    uow = container.create_uow()
    async with uow:
        reaction_repo = SqlAlchemyReactionRepository(uow.session)
        post_repo = SqlAlchemyPostRepository(uow.session)
        use_case = ReactToPostUseCase(
            reaction_repo=reaction_repo, post_repo=post_repo, uow=uow
        )
        result = await use_case.execute(
            ReactToPostDTO(
                post_id=post_id,
                user_id=current_user_id,
                reaction_type=body.reaction_type,
            )
        )

    asyncio.create_task(
        _notify_reaction(container, post_id, current_user_id, body.reaction_type)
    )
    await container.cache.invalidate_post(post_id)

    return success_response(
        ReactionResponse(
            id=result.id,
            post_id=result.post_id,
            user_id=result.user_id,
            reaction_type=result.reaction_type,
            created_at=result.created_at,
        ).model_dump(),
        status_code=201,
    )


@router.delete("/posts/{post_id}/reactions", status_code=204)
async def remove_reaction(
    post_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> Response:
    """Remove the current user's reaction from a post."""
    uow = container.create_uow()
    async with uow:
        reaction_repo = SqlAlchemyReactionRepository(uow.session)
        post_repo = SqlAlchemyPostRepository(uow.session)
        use_case = RemoveReactionUseCase(
            reaction_repo=reaction_repo, post_repo=post_repo, uow=uow
        )
        await use_case.execute(
            RemoveReactionDTO(
                post_id=post_id,
                user_id=current_user_id,
            )
        )

    await container.cache.invalidate_post(post_id)

    return Response(status_code=204)


@router.get("/posts/{post_id}/reactions")
async def get_reactions(
    post_id: str,
    limit: int = 20,
    offset: int = 0,
    container: Container = Depends(get_container),
) -> Response:
    """Get paginated reactions for a post with counts by type."""
    from fb.domain.shared.entity_id import EntityId as EId

    async with container.session_factory() as session:
        reaction_repo = SqlAlchemyReactionRepository(session)
        pid = EId.from_str(post_id)
        reactions = await reaction_repo.find_by_post(pid, limit, offset)
        total = await reaction_repo.count_by_post(pid)
        type_counts = await reaction_repo.count_by_type(pid)

    counts = {rt.value: count for rt, count in type_counts.items()}

    return success_response(
        ReactionsListResponse(
            reactions=[
                ReactionResponse(
                    id=str(r.id),
                    post_id=str(r.post_id),
                    user_id=str(r.user_id),
                    reaction_type=r.reaction_type.value,
                    created_at=str(r.created_at) if r.created_at else None,
                )
                for r in reactions
            ],
            counts=counts,
            total_count=total,
        ).model_dump(),
    )


# ── Share Endpoints ─────────────────────────────────────────────────────


@router.post("/posts/{post_id}/share", status_code=201)
async def share_post(
    post_id: str,
    body: ShareRequest,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> Response:
    """Share a post with an optional caption."""
    uow = container.create_uow()
    async with uow:
        share_repo = SqlAlchemyShareRepository(uow.session)
        post_repo = SqlAlchemyPostRepository(uow.session)
        use_case = SharePostUseCase(
            share_repo=share_repo, post_repo=post_repo, uow=uow
        )
        result = await use_case.execute(
            SharePostDTO(
                post_id=post_id,
                user_id=current_user_id,
                content=body.content,
            )
        )

    asyncio.create_task(_notify_share(container, post_id, current_user_id))

    return success_response(
        ShareResponse(
            id=result.id,
            post_id=result.post_id,
            user_id=result.user_id,
            content=result.content,
            created_at=result.created_at,
        ).model_dump(),
        status_code=201,
    )


@router.delete("/posts/{post_id}/shares/{share_id}", status_code=204)
async def delete_share(
    post_id: str,
    share_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> Response:
    """Delete a share. Only the sharer can delete it."""
    uow = container.create_uow()
    async with uow:
        share_repo = SqlAlchemyShareRepository(uow.session)
        use_case = DeleteShareUseCase(share_repo=share_repo, uow=uow)
        await use_case.execute(
            DeleteShareDTO(
                share_id=share_id,
                user_id=current_user_id,
            )
        )

    return Response(status_code=204)


@router.get("/posts/{post_id}/shares")
async def get_shares(
    post_id: str,
    limit: int = 20,
    offset: int = 0,
    container: Container = Depends(get_container),
) -> Response:
    """Get paginated shares for a post."""
    from fb.domain.shared.entity_id import EntityId as EId

    async with container.session_factory() as session:
        share_repo = SqlAlchemyShareRepository(session)
        pid = EId.from_str(post_id)
        shares = await share_repo.find_by_post(pid, limit, offset)
        total = await share_repo.count_by_post(pid)

    items = [
        ShareResponse(
            id=str(s.id),
            post_id=str(s.post_id),
            user_id=str(s.user_id),
            content=s.content,
            created_at=str(s.created_at) if s.created_at else None,
        ).model_dump()
        for s in shares
    ]

    return paginated_response(
        items,
        total=total,
        limit=limit,
        has_next=offset + limit < total,
    )


# ── Media Endpoints ───────────────────────────────────────────────────


@router.post("/posts/{post_id}/media", status_code=201)
async def upload_media(
    post_id: str,
    file: UploadFile = File(...),
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> Response:
    """Upload a media file (image/video) to a post."""
    file_data = await file.read()
    content_type = file.content_type or "application/octet-stream"
    filename = file.filename or "upload"

    use_case = UploadMediaUseCase(file_storage=container.file_storage)
    result = await use_case.execute(
        UploadMediaInput(
            post_id=post_id,
            file_data=file_data,
            filename=filename,
            content_type=content_type,
        )
    )

    return success_response(
        MediaUploadResponse(
            url=result.url,
            content_type=result.content_type,
            file_size=result.file_size,
        ).model_dump(),
        status_code=201,
    )


@router.delete("/posts/{post_id}/media/{media_id}", status_code=204)
async def delete_media(
    post_id: str,
    media_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> Response:
    """Delete a media attachment from a post."""
    # For now, delete via storage backend using media_id as the URL key
    await container.file_storage.delete(media_id)
    return Response(status_code=204)
