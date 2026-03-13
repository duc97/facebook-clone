from __future__ import annotations

from fb.domain.shared.entity_id import EntityId
from fb.domain.post.value_objects import PostContent
from fb.domain.post.repository import PostRepository
from fb.domain.post.exceptions import PostNotFoundError, PostPermissionError
from fb.application.shared.interfaces import UnitOfWork
from fb.application.post.dtos import UpdatePostInput, PostOutput


class UpdatePostUseCase:
    def __init__(self, post_repo: PostRepository, uow: UnitOfWork) -> None:
        self._post_repo = post_repo
        self._uow = uow

    async def execute(self, input_data: UpdatePostInput) -> PostOutput:
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
                    raise PostPermissionError("User can only update their own posts")

                # Update content if provided
                updated_post = post
                if input_data.content is not None:
                    # Validate new content
                    PostContent(value=input_data.content)
                    updated_post = post.update_content(input_data.content)

                # Save updated post
                saved_post = await self._post_repo.update(updated_post)

                # Commit transaction
                await self._uow.commit()

                # Return output DTO
                return PostOutput(
                    id=str(saved_post.id),
                    author_id=str(saved_post.author_id),
                    content=saved_post.content,
                    media_urls=list(saved_post.media_urls),
                    like_count=saved_post.like_count,
                    comment_count=saved_post.comment_count,
                    is_published=saved_post.is_published,
                    created_at=saved_post.created_at.isoformat() if saved_post.created_at else None,
                )

            except Exception:
                await self._uow.rollback()
                raise