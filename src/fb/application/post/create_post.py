from __future__ import annotations

from fb.domain.shared.entity_id import EntityId
from fb.domain.post.entities import Post
from fb.domain.post.value_objects import PostContent
from fb.domain.post.repository import PostRepository
from fb.application.shared.interfaces import UnitOfWork
from fb.application.post.dtos import CreatePostInput, PostOutput


class CreatePostUseCase:
    def __init__(self, post_repo: PostRepository, uow: UnitOfWork) -> None:
        self._post_repo = post_repo
        self._uow = uow

    async def execute(self, input_data: CreatePostInput) -> PostOutput:
        async with self._uow:
            try:
                # Validate content using value object
                PostContent(value=input_data.content)

                # Convert author_id to EntityId
                author_id = EntityId.from_str(input_data.author_id)

                # Convert media_urls to tuple
                media_urls = tuple(input_data.media_urls or [])

                # Create post entity
                post = Post.create(
                    author_id=author_id,
                    content=input_data.content,
                    media_urls=media_urls,
                )

                # Save to repository
                saved_post = await self._post_repo.save(post)

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