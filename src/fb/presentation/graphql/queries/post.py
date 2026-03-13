from __future__ import annotations

import strawberry
from strawberry.types import Info

from fb.presentation.graphql.context import GraphQLContext
from fb.presentation.graphql.types.post import PostType
from fb.application.post.dtos import (
    GetPostInput as GetPostApplicationInput,
    GetPostsByAuthorInput as GetPostsByAuthorApplicationInput,
)


@strawberry.type
class PostQuery:
    @strawberry.field
    async def post(self, info: Info[GraphQLContext], post_id: strawberry.ID) -> PostType | None:
        # Get dependencies from container
        container = info.context.container
        use_case = container.get_post_use_case()

        try:
            # Convert to application DTO
            app_input = GetPostApplicationInput(post_id=str(post_id))

            # Execute use case
            result = await use_case.execute(app_input)

            # Convert to GraphQL type
            return PostType(
                id=strawberry.ID(result.id),
                author_id=result.author_id,
                content=result.content,
                media_urls=result.media_urls,
                like_count=result.like_count,
                comment_count=result.comment_count,
                is_published=result.is_published,
            )
        except Exception:
            return None

    @strawberry.field
    async def posts_by_author(
        self,
        info: Info[GraphQLContext],
        author_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[PostType]:
        # Get dependencies from container
        container = info.context.container
        use_case = container.get_post_use_case()

        # Convert to application DTO
        app_input = GetPostsByAuthorApplicationInput(
            author_id=author_id,
            limit=limit,
            offset=offset,
        )

        # Execute use case
        results = await use_case.execute_by_author(app_input)

        # Convert to GraphQL types
        return [
            PostType(
                id=strawberry.ID(result.id),
                author_id=result.author_id,
                content=result.content,
                media_urls=result.media_urls,
                like_count=result.like_count,
                comment_count=result.comment_count,
                is_published=result.is_published,
            )
            for result in results
        ]