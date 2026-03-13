from __future__ import annotations

from fb.application.profile.dtos import ProfileOutput
from fb.domain.auth.repository import UserRepository
from fb.domain.profile.repository import ProfileRepository
from fb.domain.shared.entity_id import EntityId


class GetProfileUseCase:
    """Get a user's profile by user ID."""

    def __init__(
        self,
        profile_repo: ProfileRepository,
        user_repo: UserRepository,
    ) -> None:
        self._profile_repo = profile_repo
        self._user_repo = user_repo

    async def execute(self, user_id: str) -> ProfileOutput | None:
        entity_id = EntityId.from_str(user_id)

        profile = await self._profile_repo.find_by_user_id(entity_id)
        if profile is None:
            return None

        user = await self._user_repo.find_by_id(entity_id)
        display_name = user.display_name if user else ""

        return ProfileOutput(
            id=str(profile.id),
            user_id=str(profile.user_id),
            bio=profile.bio,
            avatar_url=profile.avatar_url,
            cover_photo_url=profile.cover_photo_url,
            location=profile.location,
            website=profile.website,
            display_name=display_name,
        )
