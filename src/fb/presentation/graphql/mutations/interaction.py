from __future__ import annotations

import strawberry

from fb.application.post.create_comment import CreateCommentUseCase
from fb.application.post.delete_comment import DeleteCommentUseCase
from fb.application.post.interaction_dtos import (
    CreateCommentInput,
    DeleteCommentInput,
    LikePostInput,
    UnlikePostInput,
)
from fb.application.post.like_post import LikePostUseCase
from fb.application.post.unlike_post import UnlikePostUseCase
from fb.infrastructure.repositories.comment_repo import SqlAlchemyCommentRepository
from fb.infrastructure.repositories.like_repo import SqlAlchemyLikeRepository
from fb.infrastructure.repositories.post_repo import SqlAlchemyPostRepository
from fb.presentation.graphql.context import GraphQLContext
from fb.presentation.graphql.types.auth import MessageResponse
from fb.presentation.graphql.types.interaction import CommentType, LikeType


@strawberry.type
class InteractionMutation:
    @strawberry.mutation
    async def create_comment(
        self, info: strawberry.types.Info, post_id: strawberry.ID, content: str
    ) -> CommentType | None:
        ctx: GraphQLContext = info.context
        if not ctx.is_authenticated:
            return None

        container = ctx.container
        uow = container.create_uow()
        async with uow:
            comment_repo = SqlAlchemyCommentRepository(uow.session)
            post_repo = SqlAlchemyPostRepository(uow.session)
            use_case = CreateCommentUseCase(
                comment_repo=comment_repo, post_repo=post_repo, uow=uow
            )
            result = await use_case.execute(
                CreateCommentInput(
                    post_id=str(post_id),
                    author_id=ctx.current_user_id,  # type: ignore[arg-type]
                    content=content,
                )
            )

        return CommentType(
            id=strawberry.ID(result.id),
            post_id=result.post_id,
            author_id=result.author_id,
            content=result.content,
            created_at=result.created_at,
        )

    @strawberry.mutation
    async def delete_comment(
        self, info: strawberry.types.Info, comment_id: strawberry.ID
    ) -> MessageResponse | None:
        ctx: GraphQLContext = info.context
        if not ctx.is_authenticated:
            return None

        container = ctx.container
        uow = container.create_uow()
        async with uow:
            comment_repo = SqlAlchemyCommentRepository(uow.session)
            post_repo = SqlAlchemyPostRepository(uow.session)
            use_case = DeleteCommentUseCase(
                comment_repo=comment_repo, post_repo=post_repo, uow=uow
            )
            await use_case.execute(
                DeleteCommentInput(
                    comment_id=str(comment_id),
                    user_id=ctx.current_user_id,  # type: ignore[arg-type]
                )
            )

        return MessageResponse(message="Comment deleted", success=True)

    @strawberry.mutation
    async def like_post(
        self, info: strawberry.types.Info, post_id: strawberry.ID
    ) -> LikeType | None:
        ctx: GraphQLContext = info.context
        if not ctx.is_authenticated:
            return None

        container = ctx.container
        uow = container.create_uow()
        async with uow:
            like_repo = SqlAlchemyLikeRepository(uow.session)
            post_repo = SqlAlchemyPostRepository(uow.session)
            use_case = LikePostUseCase(
                like_repo=like_repo, post_repo=post_repo, uow=uow
            )
            result = await use_case.execute(
                LikePostInput(
                    post_id=str(post_id),
                    user_id=ctx.current_user_id,  # type: ignore[arg-type]
                )
            )

        return LikeType(
            id=strawberry.ID(result.id),
            post_id=result.post_id,
            user_id=result.user_id,
        )

    @strawberry.mutation
    async def unlike_post(
        self, info: strawberry.types.Info, post_id: strawberry.ID
    ) -> MessageResponse | None:
        ctx: GraphQLContext = info.context
        if not ctx.is_authenticated:
            return None

        container = ctx.container
        uow = container.create_uow()
        async with uow:
            like_repo = SqlAlchemyLikeRepository(uow.session)
            post_repo = SqlAlchemyPostRepository(uow.session)
            use_case = UnlikePostUseCase(
                like_repo=like_repo, post_repo=post_repo, uow=uow
            )
            await use_case.execute(
                UnlikePostInput(
                    post_id=str(post_id),
                    user_id=ctx.current_user_id,  # type: ignore[arg-type]
                )
            )

        return MessageResponse(message="Post unliked", success=True)
