from __future__ import annotations

from fb.application.friend.dtos import FriendListOutput, MutualFriendsInput
from fb.domain.friend.repository import FriendRepository
from fb.domain.shared.entity_id import EntityId


class MutualFriendsUseCase:
    """Get list of mutual friends between two users."""

    def __init__(self, friend_repo: FriendRepository) -> None:
        self._friend_repo = friend_repo

    async def execute(self, input_data: MutualFriendsInput) -> FriendListOutput:
        user_id = EntityId.from_str(input_data.user_id)
        other_id = EntityId.from_str(input_data.other_id)

        mutual_ids = await self._friend_repo.get_mutual_friends(user_id, other_id)

        return FriendListOutput(
            friend_ids=[str(mid) for mid in mutual_ids],
            total_count=len(mutual_ids),
        )
