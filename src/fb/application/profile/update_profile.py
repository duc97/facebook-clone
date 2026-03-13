from __future__ import annotations

from fb.application.profile.dtos import ProfileOutput, UpdateProfileInput
from fb.application.shared.interfaces import UnitOfWork
from fb.domain.auth.repository import UserRepository
from fb.domain.profile.entities import Profile
from fb.domain.profile.repository import ProfileRepository
from fb.domain.shared.entity_id import EntityId


class UpdateProfileUseCase:
    """Update a user's profile. Creates profile if it does not exist."""

    def __init__(
        self,
        profile_repo: ProfileRepository,
        user_repo: UserRepository,
        uow: UnitOfWork,
    ) -> None:
        self._profile_repo = profile_repo
        self._user_repo = user_repo
        self._uow = uow

    async def execute(self, input_data: UpdateProfileInput) -> ProfileOutput:
        entity_id = EntityId.from_str(input_data.user_id)

        async with self._uow:
            profile = await self._profile_repo.find_by_user_id(entity_id)

            if profile is None:
                # Create new profile
                profile = Profile.create(
                    user_id=entity_id,
                    bio=input_data.bio or "",
                    location=input_data.location,
                    website=input_data.website,
                )
                profile = await self._profile_repo.save(profile)
            else:
                # Update existing profile fields
                if input_data.bio is not None:
                    profile = profile.update_bio(input_data.bio)
                if input_data.location is not None:
                    profile = profile.update_location(input_data.location)
                if input_data.website is not None:
                    profile = profile.update_website(input_data.website)
                profile = await self._profile_repo.update(profile)

            await self._uow.commit()

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
