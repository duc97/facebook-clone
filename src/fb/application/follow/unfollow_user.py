from __future__ import annotations

from fb.application.follow.dtos import UnfollowInput
from fb.application.shared.interfaces import UnitOfWork
from fb.domain.follow.exceptions import NotFollowingError
from fb.domain.follow.repository import FollowRepository
from fb.domain.shared.entity_id import EntityId


class UnfollowUserUseCase:
    """Unfollow a user."""

    def __init__(
        self,
        follow_repo: FollowRepository,
        uow: UnitOfWork,
    ) -> None:
        self._follow_repo = follow_repo
        self._uow = uow

    async def execute(self, input_data: UnfollowInput) -> None:
        follower_id = EntityId.from_str(input_data.follower_id)
        following_id = EntityId.from_str(input_data.following_id)

        async with self._uow:
            if not await self._follow_repo.is_following(follower_id, following_id):
                raise NotFollowingError()

            await self._follow_repo.delete(follower_id, following_id)
            await self._uow.commit()
