from __future__ import annotations

from typing import List, Optional

import strawberry
from fastapi import Request
from strawberry.fastapi import GraphQLRouter

from fb.container import Container
from fb.domain.shared.entity_id import EntityId
from fb.infrastructure.repositories.friend_repo import SqlAlchemyFriendRepository
from fb.infrastructure.repositories.profile_repo import SqlAlchemyProfileRepository
from fb.infrastructure.repositories.user_repo import SqlAlchemyUserRepository
from fb.infrastructure.repositories.user_search_repo import SqlAlchemyUserSearchRepository
from fb.presentation.graphql.context import GraphQLContext
from fb.presentation.graphql.middleware import get_graphql_context

# Auth
from fb.presentation.graphql.types.auth import UserType

# Profile
from fb.application.profile.dtos import ProfileOutput
from fb.application.profile.get_profile import GetProfileUseCase
from fb.presentation.graphql.types.profile import ProfileType

# Friend
from fb.application.friend.dtos import MutualFriendsInput as MutualDTO
from fb.application.friend.mutual_friends import MutualFriendsUseCase
from fb.presentation.graphql.types.friend import FriendListType, FriendRequestType

# Search
from fb.application.auth.search_dtos import SearchUsersInput
from fb.application.auth.search_users import SearchUsersUseCase
from fb.presentation.graphql.types.pagination import UserSearchResponse, UserSearchResultType

# Post
from fb.application.post.dtos import (
    GetPostInput as GetPostDTO,
    GetPostsByAuthorInput as GetPostsByAuthorDTO,
)
from fb.application.post.get_post import GetPostUseCase
from fb.infrastructure.repositories.post_repo import SqlAlchemyPostRepository
from fb.presentation.graphql.types.post import PostType

# Feed
from fb.application.post.feed_dtos import GetFeedInput
from fb.application.post.get_feed import GetFeedUseCase
from fb.infrastructure.repositories.feed_repo import SqlAlchemyFeedRepository
from fb.presentation.graphql.types.feed import FeedPostType, FeedResponse

# Interactions
from fb.application.post.get_comments import GetCommentsUseCase
from fb.infrastructure.repositories.comment_repo import SqlAlchemyCommentRepository
from fb.presentation.graphql.types.interaction import CommentType, CommentsResponse


@strawberry.type
class Query:
    # ── Auth ──
    @strawberry.field
    async def me(self, info: strawberry.types.Info) -> Optional[UserType]:
        ctx: GraphQLContext = info.context
        if not ctx.is_authenticated:
            return None
        container = ctx.container
        async with container.session_factory() as session:
            user_repo = SqlAlchemyUserRepository(session)
            user = await user_repo.find_by_id(
                EntityId.from_str(ctx.current_user_id)  # type: ignore[arg-type]
            )
        if user is None:
            return None
        return UserType(
            id=strawberry.ID(str(user.id)),
            email=str(user.email),
            display_name=user.display_name,
            is_active=user.is_active,
        )

    @strawberry.field
    async def health(self) -> str:
        return "ok"

    # ── Profile ──
    @strawberry.field
    async def profile(
        self, info: strawberry.types.Info, user_id: strawberry.ID
    ) -> Optional[ProfileType]:
        ctx: GraphQLContext = info.context
        container = ctx.container
        async with container.session_factory() as session:
            profile_repo = SqlAlchemyProfileRepository(session)
            user_repo = SqlAlchemyUserRepository(session)
            use_case = GetProfileUseCase(profile_repo=profile_repo, user_repo=user_repo)
            result = await use_case.execute(str(user_id))
        if result is None:
            return None
        return _profile_to_type(result)

    @strawberry.field
    async def my_profile(self, info: strawberry.types.Info) -> Optional[ProfileType]:
        ctx: GraphQLContext = info.context
        if not ctx.is_authenticated:
            return None
        container = ctx.container
        async with container.session_factory() as session:
            profile_repo = SqlAlchemyProfileRepository(session)
            user_repo = SqlAlchemyUserRepository(session)
            use_case = GetProfileUseCase(profile_repo=profile_repo, user_repo=user_repo)
            result = await use_case.execute(ctx.current_user_id)  # type: ignore[arg-type]
        if result is None:
            return None
        return _profile_to_type(result)

    # ── Friend ──
    @strawberry.field
    async def friends(
        self, info: strawberry.types.Info, user_id: strawberry.ID
    ) -> FriendListType:
        ctx: GraphQLContext = info.context
        container = ctx.container
        async with container.session_factory() as session:
            friend_repo = SqlAlchemyFriendRepository(session)
            uid = EntityId.from_str(str(user_id))
            friend_ids = await friend_repo.get_friends(uid)
            total_count = await friend_repo.get_friend_count(uid)
        return FriendListType(
            friend_ids=[str(fid) for fid in friend_ids],
            total_count=total_count,
        )

    @strawberry.field
    async def pending_requests(
        self, info: strawberry.types.Info
    ) -> Optional[List[FriendRequestType]]:
        ctx: GraphQLContext = info.context
        if not ctx.is_authenticated:
            return None
        container = ctx.container
        async with container.session_factory() as session:
            friend_repo = SqlAlchemyFriendRepository(session)
            uid = EntityId.from_str(ctx.current_user_id)  # type: ignore[arg-type]
            requests = await friend_repo.get_pending_requests(uid)
        return [
            FriendRequestType(
                id=strawberry.ID(str(req.id)),
                sender_id=str(req.sender_id),
                receiver_id=str(req.receiver_id),
                status=req.status.value,
            )
            for req in requests
        ]

    @strawberry.field
    async def mutual_friends(
        self, info: strawberry.types.Info, other_id: strawberry.ID
    ) -> Optional[FriendListType]:
        ctx: GraphQLContext = info.context
        if not ctx.is_authenticated:
            return None
        container = ctx.container
        async with container.session_factory() as session:
            friend_repo = SqlAlchemyFriendRepository(session)
            use_case = MutualFriendsUseCase(friend_repo)
            result = await use_case.execute(
                MutualDTO(
                    user_id=ctx.current_user_id,  # type: ignore[arg-type]
                    other_id=str(other_id),
                )
            )
        return FriendListType(friend_ids=result.friend_ids, total_count=result.total_count)

    # ── Search ──
    @strawberry.field
    async def search_users(
        self,
        info: strawberry.types.Info,
        query: str,
        limit: int = 20,
        offset: int = 0,
    ) -> UserSearchResponse:
        ctx: GraphQLContext = info.context
        container = ctx.container
        async with container.session_factory() as session:
            search_repo = SqlAlchemyUserSearchRepository(session)
            use_case = SearchUsersUseCase(search_repo)
            result = await use_case.execute(
                SearchUsersInput(query=query, limit=limit, offset=offset)
            )
        return UserSearchResponse(
            users=[
                UserSearchResultType(
                    id=strawberry.ID(u.id),
                    email=u.email,
                    display_name=u.display_name,
                    is_active=u.is_active,
                )
                for u in result.users
            ],
            total_count=result.total_count,
            has_next_page=result.has_next_page,
        )

    # ── Post ──
    @strawberry.field
    async def post(
        self, info: strawberry.types.Info, post_id: strawberry.ID
    ) -> Optional[PostType]:
        ctx: GraphQLContext = info.context
        container = ctx.container
        async with container.session_factory() as session:
            post_repo = SqlAlchemyPostRepository(session)
            use_case = GetPostUseCase(post_repo=post_repo)
            try:
                result = await use_case.execute(GetPostDTO(post_id=str(post_id)))
            except Exception:
                return None
        return PostType(
            id=strawberry.ID(result.id),
            author_id=result.author_id,
            content=result.content,
            media_urls=result.media_urls,
            like_count=result.like_count,
            comment_count=result.comment_count,
            is_published=result.is_published,
        )

    @strawberry.field
    async def posts_by_author(
        self,
        info: strawberry.types.Info,
        author_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[PostType]:
        ctx: GraphQLContext = info.context
        container = ctx.container
        async with container.session_factory() as session:
            post_repo = SqlAlchemyPostRepository(session)
            use_case = GetPostUseCase(post_repo=post_repo)
            results = await use_case.execute_by_author(
                GetPostsByAuthorDTO(author_id=author_id, limit=limit, offset=offset)
            )
        return [
            PostType(
                id=strawberry.ID(r.id),
                author_id=r.author_id,
                content=r.content,
                media_urls=r.media_urls,
                like_count=r.like_count,
                comment_count=r.comment_count,
                is_published=r.is_published,
            )
            for r in results
        ]

    # ── Feed ──
    @strawberry.field
    async def feed(
        self,
        info: strawberry.types.Info,
        limit: int = 20,
        offset: int = 0,
        first: int | None = None,
        after: str | None = None,
        mode: str = "ranked",
    ) -> Optional[FeedResponse]:
        ctx: GraphQLContext = info.context
        if not ctx.is_authenticated:
            return None
        container = ctx.container
        async with container.session_factory() as session:
            feed_repo = SqlAlchemyFeedRepository(session)
            friend_repo = SqlAlchemyFriendRepository(session)
            use_case = GetFeedUseCase(feed_repo=feed_repo, friend_repo=friend_repo)

            # Use cursor if provided
            if first is not None or after is not None:
                from fb.application.post.feed_dtos import GetFeedCursorInput

                result = await use_case.execute_cursor(
                    GetFeedCursorInput(
                        user_id=ctx.current_user_id,  # type: ignore[arg-type]
                        first=first or 20,
                        after=after,
                    )
                )
                return FeedResponse(
                    posts=[
                        FeedPostType(
                            id=strawberry.ID(p.id),
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
                    has_next_page=result.page_info["has_next_page"],
                    end_cursor=result.page_info.get("end_cursor"),
                    start_cursor=result.page_info.get("start_cursor"),
                )

            # Use ranked feed (supports both "ranked" and "chronological" modes)
            from fb.application.post.feed_dtos import GetRankedFeedInput

            result = await use_case.execute_ranked(
                GetRankedFeedInput(
                    user_id=ctx.current_user_id,  # type: ignore[arg-type]
                    limit=limit,
                    mode=mode,
                )
            )
        return FeedResponse(
            posts=[
                FeedPostType(
                    id=strawberry.ID(p.id),
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

    # ── Comments ──
    @strawberry.field
    async def comments(
        self,
        info: strawberry.types.Info,
        post_id: strawberry.ID,
        limit: int = 20,
        offset: int = 0,
    ) -> CommentsResponse:
        ctx: GraphQLContext = info.context
        container = ctx.container
        async with container.session_factory() as session:
            comment_repo = SqlAlchemyCommentRepository(session)
            use_case = GetCommentsUseCase(comment_repo=comment_repo)
            result = await use_case.execute(str(post_id), limit, offset)
        return CommentsResponse(
            comments=[
                CommentType(
                    id=strawberry.ID(c.id),
                    post_id=c.post_id,
                    author_id=c.author_id,
                    content=c.content,
                    created_at=c.created_at,
                )
                for c in result.comments
            ],
            total_count=result.total_count,
            has_next_page=result.has_next_page,
        )


schema = strawberry.Schema(query=Query)


def create_graphql_router(container: Container) -> GraphQLRouter:
    async def get_context(request: Request) -> GraphQLContext:
        return await get_graphql_context(request, container)

    return GraphQLRouter(
        schema,
        context_getter=get_context,
    )


def _profile_to_type(output: ProfileOutput) -> ProfileType:
    return ProfileType(
        id=strawberry.ID(output.id),
        user_id=strawberry.ID(output.user_id),
        bio=output.bio,
        avatar_url=output.avatar_url,
        cover_photo_url=output.cover_photo_url,
        location=output.location,
        website=output.website,
        display_name=output.display_name,
    )
