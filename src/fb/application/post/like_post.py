from __future__ import annotations

from fb.domain.shared.entity_id import EntityId
from fb.domain.post.like import Like
from fb.domain.post.like_repository import LikeRepository
from fb.domain.post.repository import PostRepository
from fb.domain.post.exceptions import PostNotFoundError
from fb.domain.post.interaction_exceptions import AlreadyLikedError
from fb.application.shared.interfaces import UnitOfWork
from fb.application.post.interaction_dtos import LikePostInput, LikeOutput


class LikePostUseCase:
    def __init__(
        self,
        like_repo: LikeRepository,
        post_repo: PostRepository,
        uow: UnitOfWork,
    ) -> None:
        self._like_repo = like_repo
        self._post_repo = post_repo
        self._uow = uow

    async def execute(self, input_data: LikePostInput) -> LikeOutput:
        post_id = EntityId.from_str(input_data.post_id)
        user_id = EntityId.from_str(input_data.user_id)

        # Find post to ensure it exists
        post = await self._post_repo.find_by_id(post_id)
        if not post:
            raise PostNotFoundError(f"Post with id {input_data.post_id} not found")

        # Check if user already liked this post
        existing_like = await self._like_repo.find_by_post_and_user(post_id, user_id)
        if existing_like:
            raise AlreadyLikedError("User has already liked this post")

        # Create like
        like = Like.create(post_id=post_id, user_id=user_id)

        # Save like
        saved_like = await self._like_repo.save(like)

        # Increment post like count
        updated_post = post.increment_like_count()
        await self._post_repo.update(updated_post)

        # Commit transaction
        await self._uow.commit()

        return LikeOutput(
            id=str(saved_like.id),
            post_id=str(saved_like.post_id),
            user_id=str(saved_like.user_id),
        )