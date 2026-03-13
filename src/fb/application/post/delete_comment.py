from __future__ import annotations

from fb.domain.shared.entity_id import EntityId
from fb.domain.post.comment_repository import CommentRepository
from fb.domain.post.repository import PostRepository
from fb.domain.post.interaction_exceptions import CommentNotFoundError, CommentPermissionError
from fb.application.shared.interfaces import UnitOfWork
from fb.application.post.interaction_dtos import DeleteCommentInput


class DeleteCommentUseCase:
    def __init__(
        self,
        comment_repo: CommentRepository,
        post_repo: PostRepository,
        uow: UnitOfWork,
    ) -> None:
        self._comment_repo = comment_repo
        self._post_repo = post_repo
        self._uow = uow

    async def execute(self, input_data: DeleteCommentInput) -> None:
        comment_id = EntityId.from_str(input_data.comment_id)
        user_id = EntityId.from_str(input_data.user_id)

        # Find comment to ensure it exists
        comment = await self._comment_repo.find_by_id(comment_id)
        if not comment:
            raise CommentNotFoundError(f"Comment with id {input_data.comment_id} not found")

        # Check authorization - only comment author can delete
        if comment.author_id != user_id:
            raise CommentPermissionError("Only the comment author can delete this comment")

        # Find post to decrement comment count
        post = await self._post_repo.find_by_id(comment.post_id)
        if post:
            updated_post = post.decrement_comment_count()
            await self._post_repo.update(updated_post)

        # Delete comment
        await self._comment_repo.delete(comment_id)

        # Commit transaction
        await self._uow.commit()