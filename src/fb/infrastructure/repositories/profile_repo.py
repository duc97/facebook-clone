from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fb.domain.profile.entities import Profile
from fb.domain.shared.entity_id import EntityId
from fb.infrastructure.database.models.profile import ProfileModel


class SqlAlchemyProfileRepository:
    """SQLAlchemy implementation of ProfileRepository protocol."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_user_id(self, user_id: EntityId) -> Profile | None:
        result = await self._session.execute(
            select(ProfileModel).where(ProfileModel.user_id == user_id.value)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def save(self, profile: Profile) -> Profile:
        model = ProfileModel(
            user_id=profile.user_id.value,
            bio=profile.bio,
        )
        # Override the auto-generated id with our domain id
        model.id = profile.id.value
        # Set optional fields
        model.avatar_url = profile.avatar_url
        model.cover_photo_url = profile.cover_photo_url
        model.location = profile.location
        model.website = profile.website
        model.date_of_birth = profile.date_of_birth
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def update(self, profile: Profile) -> Profile:
        result = await self._session.execute(
            select(ProfileModel).where(ProfileModel.user_id == profile.user_id.value)
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise ValueError(f"Profile for user {profile.user_id} not found")
        model.bio = profile.bio
        model.avatar_url = profile.avatar_url
        model.cover_photo_url = profile.cover_photo_url
        model.location = profile.location
        model.website = profile.website
        model.date_of_birth = profile.date_of_birth
        await self._session.flush()
        return self._to_entity(model)

    async def exists_by_user_id(self, user_id: EntityId) -> bool:
        result = await self._session.execute(
            select(ProfileModel.id).where(ProfileModel.user_id == user_id.value).limit(1)
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    def _to_entity(model: ProfileModel) -> Profile:
        return Profile(
            id=EntityId(model.id),
            user_id=EntityId(model.user_id),
            bio=model.bio,
            avatar_url=model.avatar_url,
            cover_photo_url=model.cover_photo_url,
            location=model.location,
            website=model.website,
            date_of_birth=model.date_of_birth,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
