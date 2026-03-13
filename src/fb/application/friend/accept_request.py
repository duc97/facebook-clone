from __future__ import annotations

from fb.application.friend.dtos import AcceptRequestInput, FriendRequestOutput
from fb.application.shared.interfaces import UnitOfWork
from fb.domain.friend.entities import Friendship
from fb.domain.friend.exceptions import FriendRequestNotFoundError
from fb.domain.friend.repository import FriendRepository
from fb.domain.friend.value_objects import FriendRequestStatus
from fb.domain.shared.entity_id import EntityId


class AcceptRequestUseCase:
    """Accept a pending friend request."""

    def __init__(
        self,
        friend_repo: FriendRepository,
        uow: UnitOfWork,
    ) -> None:
        self._friend_repo = friend_repo
        self._uow = uow

    async def execute(self, input_data: AcceptRequestInput) -> FriendRequestOutput:
        request_id = EntityId.from_str(input_data.request_id)
        user_id = EntityId.from_str(input_data.user_id)

        async with self._uow:
            # Find the request
            friend_request = await self._friend_repo.find_request_by_id(request_id)

            # Validate: exists, is pending, and receiver matches
            if friend_request is None:
                raise FriendRequestNotFoundError()
            if friend_request.status != FriendRequestStatus.PENDING:
                raise FriendRequestNotFoundError()
            if friend_request.receiver_id != user_id:
                raise FriendRequestNotFoundError()

            # Accept the request
            accepted = friend_request.accept()
            await self._friend_repo.update_request(accepted)

            # Create bi-directional friendship
            f1, f2 = Friendship.create_pair(
                user_id=accepted.sender_id,
                friend_id=accepted.receiver_id,
            )
            await self._friend_repo.save_friendship(f1)
            await self._friend_repo.save_friendship(f2)

            await self._uow.commit()

            return FriendRequestOutput(
                id=str(accepted.id),
                sender_id=str(accepted.sender_id),
                receiver_id=str(accepted.receiver_id),
                status=accepted.status.value,
            )
