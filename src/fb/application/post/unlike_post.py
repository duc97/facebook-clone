from __future__ import annotations

from fb.domain.shared.entity_id import EntityId
from fb.domain.post.like_repository import LikeRepository
from fb.domain.post.repository import PostRepository
from fb.domain.post.interaction_exceptions import NotLikedError
from fb.application.shared.interfaces import UnitOfWork
from fb.application.post.interaction_dtos import UnlikePostInput


class UnlikePostUseCase:
    def __init__(
        self,
        like_repo: LikeRepository,
        post_repo: PostRepository,
        uow: UnitOfWork,
    ) -> None:
        self._like_repo = like_repo
        self._post_repo = post_repo
        self._uow = uow

    async def execute(self, input_data: UnlikePostInput) -> None:
        post_id = EntityId.from_str(input_data.post_id)
        user_id = EntityId.from_str(input_data.user_id)

        # Find like to ensure it exists
        like = await self._like_repo.find_by_post_and_user(post_id, user_id)
        if not like:
            raise NotLikedError("User has not liked this post")

        # Find post to decrement like count
        post = await self._post_repo.find_by_id(post_id)
        if post:
            updated_post = post.decrement_like_count()
            await self._post_repo.update(updated_post)

        # Delete like
        await self._like_repo.delete(like.id)

        # Commit transaction
        await self._uow.commit()