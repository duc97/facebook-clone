from __future__ import annotations

import strawberry
import strawberry.types

from fb.application.post.feed_dtos import GetFeedInput
from fb.application.post.get_feed import GetFeedUseCase
from fb.presentation.graphql.context import GraphQLContext
from fb.presentation.graphql.types.feed import FeedPostType, FeedResponse


@strawberry.type
class FeedQuery:
    """GraphQL queries for feed functionality."""

    @strawberry.field
    async def feed(
        self,
        info: strawberry.types.Info,
        limit: int = 20,
        offset: int = 0
    ) -> FeedResponse | None:
        """Get user's feed with posts from user and friends."""
        ctx: GraphQLContext = info.context

        if not ctx.is_authenticated:
            return None

        # Get use case from container
        use_case: GetFeedUseCase = ctx.container.get(GetFeedUseCase)

        # Execute use case
        input_data = GetFeedInput(
            user_id=str(ctx.current_user_id),
            limit=limit,
            offset=offset
        )

        result = await use_case.execute(input_data)

        # Convert to GraphQL types
        return FeedResponse(
            posts=[
                FeedPostType(
                    id=strawberry.ID(post.id),
                    author_id=post.author_id,
                    content=post.content,
                    media_urls=post.media_urls,
                    like_count=post.like_count,
                    comment_count=post.comment_count,
                    created_at=post.created_at,
                )
                for post in result.posts
            ],
            total_count=result.total_count,
            has_next_page=result.has_next_page,
        )