from __future__ import annotations

import strawberry
from strawberry.types import Info

from fb.application.post.get_comments import GetCommentsUseCase
from fb.presentation.graphql.types.interaction import CommentsResponse, CommentType


@strawberry.type
class InteractionQuery:
    @strawberry.field
    async def comments(
        self, info: Info, post_id: strawberry.ID, limit: int = 20, offset: int = 0
    ) -> CommentsResponse:
        # Get use case from container
        use_case: GetCommentsUseCase = info.context.container.get_comments_use_case()

        result = await use_case.execute(str(post_id), limit, offset)

        comment_types = [
            CommentType(
                id=strawberry.ID(comment.id),
                post_id=comment.post_id,
                author_id=comment.author_id,
                content=comment.content,
                created_at=comment.created_at,
            )
            for comment in result.comments
        ]

        return CommentsResponse(
            comments=comment_types,
            total_count=result.total_count,
            has_next_page=result.has_next_page,
        )