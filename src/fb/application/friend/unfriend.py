from __future__ import annotations

from fb.application.friend.dtos import UnfriendInput
from fb.application.shared.interfaces import UnitOfWork
from fb.domain.friend.exceptions import NotFriendsError
from fb.domain.friend.repository import FriendRepository
from fb.domain.shared.entity_id import EntityId


class UnfriendUseCase:
    """Remove a friendship (both directions)."""

    def __init__(
        self,
        friend_repo: FriendRepository,
        uow: UnitOfWork,
    ) -> None:
        self._friend_repo = friend_repo
        self._uow = uow

    async def execute(self, input_data: UnfriendInput) -> None:
        user_id = EntityId.from_str(input_data.user_id)
        friend_id = EntityId.from_str(input_data.friend_id)

        async with self._uow:
            # Validate they are friends
            if not await self._friend_repo.are_friends(user_id, friend_id):
                raise NotFriendsError()

            # Delete both directions
            await self._friend_repo.delete_friendship(user_id, friend_id)
            await self._uow.commit()
