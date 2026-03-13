from __future__ import annotations

from fb.application.friend.dtos import FriendRequestOutput, SendRequestInput
from fb.application.shared.interfaces import UnitOfWork
from fb.domain.friend.entities import FriendRequest
from fb.domain.friend.exceptions import (
    AlreadyFriendsError,
    CannotFriendSelfError,
    FriendRequestAlreadyExistsError,
    UserBlockedError,
)
from fb.domain.friend.repository import FriendRepository
from fb.domain.friend.value_objects import FriendRequestStatus
from fb.domain.shared.entity_id import EntityId


class SendRequestUseCase:
    """Send a friend request to another user."""

    def __init__(
        self,
        friend_repo: FriendRepository,
        uow: UnitOfWork,
    ) -> None:
        self._friend_repo = friend_repo
        self._uow = uow

    async def execute(self, input_data: SendRequestInput) -> FriendRequestOutput:
        sender_id = EntityId.from_str(input_data.sender_id)
        receiver_id = EntityId.from_str(input_data.receiver_id)

        # Cannot friend yourself
        if sender_id == receiver_id:
            raise CannotFriendSelfError()

        async with self._uow:
            # Check if already friends
            if await self._friend_repo.are_friends(sender_id, receiver_id):
                raise AlreadyFriendsError()

            # Check for existing request (either direction)
            existing = await self._friend_repo.find_request(sender_id, receiver_id)
            if existing is None:
                existing = await self._friend_repo.find_request(receiver_id, sender_id)

            if existing is not None:
                if existing.status == FriendRequestStatus.BLOCKED:
                    raise UserBlockedError()
                if existing.status == FriendRequestStatus.PENDING:
                    raise FriendRequestAlreadyExistsError()

            # Create new friend request
            friend_request = FriendRequest.create(
                sender_id=sender_id, receiver_id=receiver_id
            )
            saved = await self._friend_repo.save_request(friend_request)
            await self._uow.commit()

            return FriendRequestOutput(
                id=str(saved.id),
                sender_id=str(saved.sender_id),
                receiver_id=str(saved.receiver_id),
                status=saved.status.value,
            )
