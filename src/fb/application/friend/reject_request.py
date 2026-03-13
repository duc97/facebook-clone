from __future__ import annotations

from fb.application.friend.dtos import FriendRequestOutput, RejectRequestInput
from fb.application.shared.interfaces import UnitOfWork
from fb.domain.friend.exceptions import FriendRequestNotFoundError
from fb.domain.friend.repository import FriendRepository
from fb.domain.friend.value_objects import FriendRequestStatus
from fb.domain.shared.entity_id import EntityId


class RejectRequestUseCase:
    """Reject a pending friend request."""

    def __init__(
        self,
        friend_repo: FriendRepository,
        uow: UnitOfWork,
    ) -> None:
        self._friend_repo = friend_repo
        self._uow = uow

    async def execute(self, input_data: RejectRequestInput) -> FriendRequestOutput:
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

            # Reject the request
            rejected = friend_request.reject()
            await self._friend_repo.update_request(rejected)

            await self._uow.commit()

            return FriendRequestOutput(
                id=str(rejected.id),
                sender_id=str(rejected.sender_id),
                receiver_id=str(rejected.receiver_id),
                status=rejected.status.value,
            )
