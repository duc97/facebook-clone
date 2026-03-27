from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from fb.application.post.dtos import GetPostsByAuthorInput
from fb.application.post.get_post import GetPostUseCase
from fb.application.profile.dtos import (
    UpdateProfileInput as UpdateProfileDTO,
)
from fb.application.profile.dtos import (
    UploadAvatarInput as UploadAvatarDTO,
)
from fb.application.profile.get_profile import GetProfileUseCase
from fb.application.profile.update_profile import UpdateProfileUseCase
from fb.application.profile.upload_avatar import UploadAvatarUseCase
from fb.container import Container
from fb.domain.shared.entity_id import EntityId
from fb.infrastructure.repositories.follow_repo import SqlAlchemyFollowRepository
from fb.infrastructure.repositories.post_repo import SqlAlchemyPostRepository
from fb.infrastructure.repositories.profile_repo import SqlAlchemyProfileRepository
from fb.infrastructure.repositories.user_repo import SqlAlchemyUserRepository
from fb.presentation.dependencies import get_container, get_current_user_id
from fb.presentation.rest.response import paginated_response, success_response
from fb.presentation.rest.v1.schemas import (
    FriendListResponse,
    PostResponse,
    ProfileResponse,
    ProfileUpdateRequest,
)

router = APIRouter(tags=["users"])


@router.get("/users/online")
async def get_online_users(
    container: Container = Depends(get_container),
):
    """Get the list of currently online user IDs."""
    online_ids = list(container.connection_manager.get_online_users())
    return success_response({"online_user_ids": online_ids})


@router.get("/users/{user_id}/online")
async def get_user_online_status(
    user_id: str,
    container: Container = Depends(get_container),
):
    """Check whether a specific user is currently online."""
    is_online = container.connection_manager.is_online(user_id)
    return success_response({"user_id": user_id, "is_online": is_online})


@router.get("/users/{user_id}")
async def get_user_profile(
    user_id: str,
    container: Container = Depends(get_container),
):
    """Get a user's profile by user ID."""
    # 1. Cache check — return immediately on hit
    cached = await container.cache.get_profile(user_id)
    if cached is not None:
        return success_response(cached)

    # 2. DB fetch
    async with container.session_factory() as session:
        profile_repo = SqlAlchemyProfileRepository(session)
        user_repo = SqlAlchemyUserRepository(session)
        use_case = GetProfileUseCase(
            profile_repo=profile_repo,
            user_repo=user_repo,
        )
        result = await use_case.execute(user_id)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    # 3. Serialize, cache, and return
    data = ProfileResponse(
        id=result.id,
        user_id=result.user_id,
        bio=result.bio,
        avatar_url=result.avatar_url,
        cover_photo_url=result.cover_photo_url,
        location=result.location,
        website=result.website,
        display_name=result.display_name,
    ).model_dump()
    await container.cache.set_profile(user_id, data)
    return success_response(data)


@router.put("/users/{user_id}/profile")
async def update_user_profile(
    user_id: str,
    body: ProfileUpdateRequest,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
):
    """Update the authenticated user's profile."""
    if current_user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update another user's profile",
        )

    uow = container.create_uow()
    async with uow:
        profile_repo = SqlAlchemyProfileRepository(uow.session)
        user_repo = SqlAlchemyUserRepository(uow.session)
        use_case = UpdateProfileUseCase(
            profile_repo=profile_repo,
            user_repo=user_repo,
            uow=uow,
        )
        result = await use_case.execute(
            UpdateProfileDTO(
                user_id=user_id,
                bio=body.bio,
                location=body.location,
                website=body.website,
            )
        )

    # Invalidate cached profile so next GET fetches fresh data
    await container.cache.invalidate_profile(user_id)

    return success_response(
        ProfileResponse(
            id=result.id,
            user_id=result.user_id,
            bio=result.bio,
            avatar_url=result.avatar_url,
            cover_photo_url=result.cover_photo_url,
            location=result.location,
            website=result.website,
            display_name=result.display_name,
        ).model_dump(),
    )


@router.put("/users/{user_id}/avatar")
async def upload_user_avatar(
    user_id: str,
    file: UploadFile,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
):
    """Upload a new avatar image for the authenticated user."""
    if current_user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update another user's avatar",
        )

    file_data = await file.read()
    file_storage = container.file_storage

    uow = container.create_uow()
    async with uow:
        profile_repo = SqlAlchemyProfileRepository(uow.session)
        user_repo = SqlAlchemyUserRepository(uow.session)
        use_case = UploadAvatarUseCase(
            profile_repo=profile_repo,
            user_repo=user_repo,
            file_storage=file_storage,
            uow=uow,
        )
        result = await use_case.execute(
            UploadAvatarDTO(
                user_id=user_id,
                file_data=file_data,
                filename=file.filename or "avatar",
                content_type=file.content_type or "application/octet-stream",
            )
        )

    # Invalidate cached profile since avatar URL has changed
    await container.cache.invalidate_profile(user_id)

    return success_response(
        ProfileResponse(
            id=result.id,
            user_id=result.user_id,
            bio=result.bio,
            avatar_url=result.avatar_url,
            cover_photo_url=result.cover_photo_url,
            location=result.location,
            website=result.website,
            display_name=result.display_name,
        ).model_dump(),
    )


@router.get("/users/{user_id}/friends")
async def get_user_friends(
    user_id: str,
    limit: int = 20,
    offset: int = 0,
    container: Container = Depends(get_container),
):
    """Get a paginated list of users this user is following."""
    async with container.session_factory() as session:
        follow_repo = SqlAlchemyFollowRepository(session)
        uid = EntityId.from_str(user_id)
        friend_ids = await follow_repo.get_following(uid, limit=limit, offset=offset)
        total = await follow_repo.get_following_count(uid)

    response = FriendListResponse(
        friend_ids=[str(fid) for fid in friend_ids],
        total_count=total,
    )

    page = (offset // limit) + 1 if limit > 0 else 1
    return paginated_response(
        response.model_dump()["friend_ids"],
        total=total,
        limit=limit,
        page=page,
        has_next=(offset + limit) < total,
    )


@router.get("/users/{user_id}/posts")
async def get_user_posts(
    user_id: str,
    limit: int = 20,
    offset: int = 0,
    container: Container = Depends(get_container),
):
    """Get a paginated list of a user's posts (kept for backwards compat,
    canonical endpoint is GET /friends/{user_id}/posts)."""
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
