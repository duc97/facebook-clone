from __future__ import annotations

from fb.domain.shared.entity_id import EntityId
from fb.domain.post.repository import PostRepository
from fb.domain.post.exceptions import PostNotFoundError
from fb.application.post.dtos import GetPostInput, GetPostsByAuthorInput, PostOutput


class GetPostUseCase:
    def __init__(self, post_repo: PostRepository) -> None:
        self._post_repo = post_repo

    async def execute(self, input_data: GetPostInput) -> PostOutput:
        # Find the post
        post_id = EntityId.from_str(input_data.post_id)
        post = await self._post_repo.find_by_id(post_id)

        if not post:
            raise PostNotFoundError(f"Post with id {input_data.post_id} not found")

        # Return output DTO
        return PostOutput(
            id=str(post.id),
            author_id=str(post.author_id),
            content=post.content,
            media_urls=list(post.media_urls),
            like_count=post.like_count,
            comment_count=post.comment_count,
            is_published=post.is_published,
            created_at=post.created_at.isoformat() if post.created_at else None,
        )

    async def execute_by_author(self, input_data: GetPostsByAuthorInput) -> list[PostOutput]:
        # Find posts by author
        author_id = EntityId.from_str(input_data.author_id)
        posts = await self._post_repo.find_by_author(
            author_id=author_id,
            limit=input_data.limit,
            offset=input_data.offset,
        )

        # Convert to output DTOs
        return [
            PostOutput(
                id=str(post.id),
                author_id=str(post.author_id),
                content=post.content,
                media_urls=list(post.media_urls),
                like_count=post.like_count,
                comment_count=post.comment_count,
                is_published=post.is_published,
                created_at=post.created_at.isoformat() if post.created_at else None,
            )
            for post in posts
        ]