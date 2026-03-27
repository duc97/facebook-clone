from __future__ import annotations

from fb.application.follow.dtos import FollowInput
from fb.application.shared.interfaces import UnitOfWork
from fb.domain.follow.entities import Follow
from fb.domain.follow.exceptions import AlreadyFollowingError, CannotFollowSelfError
from fb.domain.follow.repository import FollowRepository
from fb.domain.shared.entity_id import EntityId


class FollowUserUseCase:
    """Follow another user (unidirectional)."""

    def __init__(
        self,
        follow_repo: FollowRepository,
        uow: UnitOfWork,
    ) -> None:
        self._follow_repo = follow_repo
        self._uow = uow

    async def execute(self, input_data: FollowInput) -> None:
        follower_id = EntityId.from_str(input_data.follower_id)
        following_id = EntityId.from_str(input_data.following_id)

        if follower_id == following_id:
            raise CannotFollowSelfError()

        async with self._uow:
            if await self._follow_repo.is_following(follower_id, following_id):
                raise AlreadyFollowingError()

            follow = Follow.create(follower_id=follower_id, following_id=following_id)
            await self._follow_repo.save(follow)
            await self._uow.commit()
