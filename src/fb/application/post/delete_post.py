from __future__ import annotations

from fb.domain.shared.entity_id import EntityId
from fb.domain.post.repository import PostRepository
from fb.domain.post.exceptions import PostNotFoundError, PostPermissionError
from fb.application.shared.interfaces import UnitOfWork
from fb.application.post.dtos import DeletePostInput


class DeletePostUseCase:
    def __init__(self, post_repo: PostRepository, uow: UnitOfWork) -> None:
        self._post_repo = post_repo
        self._uow = uow

    async def execute(self, input_data: DeletePostInput) -> None:
        async with self._uow:
            try:
                # Find the post
                post_id = EntityId.from_str(input_data.post_id)
                user_id = EntityId.from_str(input_data.user_id)

                post = await self._post_repo.find_by_id(post_id)
                if not post:
                    raise PostNotFoundError(f"Post with id {input_data.post_id} not found")

                # Check authorization
                if post.author_id != user_id:
                    raise PostPermissionError("User can only delete their own posts")

                # Soft delete the post (mark as unpublished)
                deleted_post = post.delete()
                await self._post_repo.update(deleted_post)

                # Commit transaction
                await self._uow.commit()

            except Exception:
                await self._uow.rollback()
                raise