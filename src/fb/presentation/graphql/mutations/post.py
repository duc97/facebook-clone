from __future__ import annotations

import strawberry

from fb.application.post.create_post import CreatePostUseCase
from fb.application.post.delete_post import DeletePostUseCase
from fb.application.post.dtos import (
    CreatePostInput as CreatePostDTO,
    DeletePostInput as DeletePostDTO,
    UpdatePostInput as UpdatePostDTO,
)
from fb.application.post.update_post import UpdatePostUseCase
from fb.infrastructure.repositories.post_repo import SqlAlchemyPostRepository
from fb.presentation.graphql.context import GraphQLContext
from fb.presentation.graphql.inputs.post import CreatePostInput, UpdatePostInput
from fb.presentation.graphql.types.auth import MessageResponse
from fb.presentation.graphql.types.post import PostType


@strawberry.type
class PostMutation:
    @strawberry.mutation
    async def create_post(
        self, info: strawberry.types.Info, input: CreatePostInput
    ) -> PostType | None:
        ctx: GraphQLContext = info.context
        if not ctx.is_authenticated:
            return None

        container = ctx.container
        uow = container.create_uow()
        async with uow:
            post_repo = SqlAlchemyPostRepository(uow.session)
            use_case = CreatePostUseCase(post_repo=post_repo, uow=uow)
            result = await use_case.execute(
                CreatePostDTO(
                    author_id=ctx.current_user_id,  # type: ignore[arg-type]
                    content=input.content,
                    media_urls=input.media_urls,
                )
            )

        return PostType(
            id=strawberry.ID(result.id),
            author_id=result.author_id,
            content=result.content,
            media_urls=result.media_urls,
            like_count=result.like_count,
            comment_count=result.comment_count,
            is_published=result.is_published,
        )

    @strawberry.mutation
    async def update_post(
        self, info: strawberry.types.Info, post_id: strawberry.ID, content: str
    ) -> PostType | None:
        ctx: GraphQLContext = info.context
        if not ctx.is_authenticated:
            return None

        container = ctx.container
        uow = container.create_uow()
        async with uow:
            post_repo = SqlAlchemyPostRepository(uow.session)
            use_case = UpdatePostUseCase(post_repo=post_repo, uow=uow)
            result = await use_case.execute(
                UpdatePostDTO(
                    post_id=str(post_id),
                    user_id=ctx.current_user_id,  # type: ignore[arg-type]
                    content=content,
                )
            )

        # Invalidate the cached post so next read reflects updated content.
        await container.cache.invalidate_post(str(post_id))

        return PostType(
            id=strawberry.ID(result.id),
            author_id=result.author_id,
            content=result.content,
            media_urls=result.media_urls,
            like_count=result.like_count,
            comment_count=result.comment_count,
            is_published=result.is_published,
        )

    @strawberry.mutation
    async def delete_post(
        self, info: strawberry.types.Info, post_id: strawberry.ID
    ) -> MessageResponse | None:
        ctx: GraphQLContext = info.context
        if not ctx.is_authenticated:
            return None

        container = ctx.container
        uow = container.create_uow()
        async with uow:
            post_repo = SqlAlchemyPostRepository(uow.session)
            use_case = DeletePostUseCase(post_repo=post_repo, uow=uow)
            await use_case.execute(
                DeletePostDTO(
                    post_id=str(post_id),
                    user_id=ctx.current_user_id,  # type: ignore[arg-type]
                )
            )

        # Remove deleted post from cache.
        await container.cache.invalidate_post(str(post_id))

        return MessageResponse(message="Post deleted", success=True)
