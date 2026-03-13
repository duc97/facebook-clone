from __future__ import annotations

from fb.application.profile.dtos import ProfileOutput, UploadAvatarInput
from fb.application.shared.interfaces import UnitOfWork
from fb.domain.auth.repository import UserRepository
from fb.domain.profile.entities import Profile
from fb.domain.profile.exceptions import InvalidFileTypeError
from fb.domain.profile.repository import ProfileRepository
from fb.domain.profile.services import FileStorage
from fb.domain.shared.entity_id import EntityId

ALLOWED_IMAGE_TYPES = frozenset({
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
})


class UploadAvatarUseCase:
    """Upload an avatar image and update the user's profile."""

    def __init__(
        self,
        profile_repo: ProfileRepository,
        user_repo: UserRepository,
        file_storage: FileStorage,
        uow: UnitOfWork,
    ) -> None:
        self._profile_repo = profile_repo
        self._user_repo = user_repo
        self._file_storage = file_storage
        self._uow = uow

    async def execute(self, input_data: UploadAvatarInput) -> ProfileOutput:
        # Validate file type before any I/O
        if input_data.content_type not in ALLOWED_IMAGE_TYPES:
            raise InvalidFileTypeError(input_data.content_type)

        entity_id = EntityId.from_str(input_data.user_id)

        # Upload file
        avatar_url = await self._file_storage.upload(
            file_data=input_data.file_data,
            filename=input_data.filename,
            content_type=input_data.content_type,
        )

        async with self._uow:
            profile = await self._profile_repo.find_by_user_id(entity_id)

            if profile is None:
                profile = Profile.create(user_id=entity_id, avatar_url=avatar_url)
                profile = await self._profile_repo.save(profile)
            else:
                profile = profile.update_avatar(avatar_url)
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
