from __future__ import annotations

from fb.domain.shared.entity_id import EntityId
from fb.domain.post.comment_repository import CommentRepository
from fb.application.post.interaction_dtos import CommentOutput, CommentsListOutput


class GetCommentsUseCase:
    def __init__(self, comment_repo: CommentRepository) -> None:
        self._comment_repo = comment_repo

    async def execute(self, post_id: str, limit: int = 20, offset: int = 0) -> CommentsListOutput:
        post_id_entity = EntityId.from_str(post_id)

        # Get comments for the post
        comments = await self._comment_repo.find_by_post(post_id_entity, limit, offset)
        total_count = await self._comment_repo.count_by_post(post_id_entity)

        # Convert to output DTOs
        comment_outputs = [
            CommentOutput(
                id=str(comment.id),
                post_id=str(comment.post_id),
                author_id=str(comment.author_id),
                content=comment.content,
                created_at=comment.created_at.isoformat() if comment.created_at else None,
            )
            for comment in comments
        ]

        # Check if there are more pages
        has_next_page = offset + len(comments) < total_count

        return CommentsListOutput(
            comments=comment_outputs,
            total_count=total_count,
            has_next_page=has_next_page,
        )