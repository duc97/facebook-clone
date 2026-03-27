from __future__ import annotations

from fb.application.follow.dtos import FollowListOutput
from fb.domain.follow.repository import FollowRepository
from fb.domain.shared.entity_id import EntityId


class GetFollowingUseCase:
    """Get list of users that a given user is following."""

    def __init__(self, follow_repo: FollowRepository) -> None:
        self._follow_repo = follow_repo

    async def execute(
        self, user_id: str, limit: int = 20, offset: int = 0
    ) -> FollowListOutput:
        uid = EntityId.from_str(user_id)
        following_ids = await self._follow_repo.get_following(uid, limit=limit, offset=offset)
        total = await self._follow_repo.get_following_count(uid)
        return FollowListOutput(
            user_ids=[str(fid) for fid in following_ids],
            total_count=total,
        )
