from __future__ import annotations

from fb.domain.shared.entity_id import EntityId
from fb.domain.post.comment import Comment
from fb.domain.post.comment_repository import CommentRepository
from fb.domain.post.repository import PostRepository
from fb.domain.post.exceptions import PostNotFoundError
from fb.application.shared.interfaces import UnitOfWork
from fb.application.post.interaction_dtos import CreateCommentInput, CommentOutput


class CreateCommentUseCase:
    def __init__(
        self,
        comment_repo: CommentRepository,
        post_repo: PostRepository,
        uow: UnitOfWork,
    ) -> None:
        self._comment_repo = comment_repo
        self._post_repo = post_repo
        self._uow = uow

    async def execute(self, input_data: CreateCommentInput) -> CommentOutput:
        post_id = EntityId.from_str(input_data.post_id)
        author_id = EntityId.from_str(input_data.author_id)

        # Find post to ensure it exists
        post = await self._post_repo.find_by_id(post_id)
        if not post:
            raise PostNotFoundError(f"Post with id {input_data.post_id} not found")

        # Create comment
        comment = Comment.create(
            post_id=post_id,
            author_id=author_id,
            content=input_data.content
        )

        # Save comment
        saved_comment = await self._comment_repo.save(comment)

        # Increment post comment count
        updated_post = post.increment_comment_count()
        await self._post_repo.update(updated_post)

        # Commit transaction
        await self._uow.commit()

        return CommentOutput(
            id=str(saved_comment.id),
            post_id=str(saved_comment.post_id),
            author_id=str(saved_comment.author_id),
            content=saved_comment.content,
            created_at=saved_comment.created_at.isoformat() if saved_comment.created_at else None,
        )