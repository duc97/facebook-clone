from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from fb.domain.shared.entity_id import EntityId


@dataclass(frozen=True, slots=True)
class Profile:
    """Profile domain entity."""

    id: EntityId
    user_id: EntityId
    bio: str
    avatar_url: str | None
    cover_photo_url: str | None
    location: str | None
    website: str | None
    date_of_birth: date | None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def create(
        cls,
        user_id: EntityId,
        bio: str = "",
        avatar_url: str | None = None,
        cover_photo_url: str | None = None,
        location: str | None = None,
        website: str | None = None,
        date_of_birth: date | None = None,
    ) -> Profile:
        """Factory method to create a new Profile."""
        return cls(
            id=EntityId.generate(),
            user_id=user_id,
            bio=bio,
            avatar_url=avatar_url,
            cover_photo_url=cover_photo_url,
            location=location,
            website=website,
            date_of_birth=date_of_birth,
        )

    def update_bio(self, bio: str) -> Profile:
        """Return a new Profile with updated bio."""
        return Profile(
            id=self.id,
            user_id=self.user_id,
            bio=bio,
            avatar_url=self.avatar_url,
            cover_photo_url=self.cover_photo_url,
            location=self.location,
            website=self.website,
            date_of_birth=self.date_of_birth,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    def update_avatar(self, url: str) -> Profile:
        """Return a new Profile with updated avatar URL."""
        return Profile(
            id=self.id,
            user_id=self.user_id,
            bio=self.bio,
            avatar_url=url,
            cover_photo_url=self.cover_photo_url,
            location=self.location,
            website=self.website,
            date_of_birth=self.date_of_birth,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    def update_cover_photo(self, url: str) -> Profile:
        """Return a new Profile with updated cover photo URL."""
        return Profile(
            id=self.id,
            user_id=self.user_id,
            bio=self.bio,
            avatar_url=self.avatar_url,
            cover_photo_url=url,
            location=self.location,
            website=self.website,
            date_of_birth=self.date_of_birth,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    def update_location(self, location: str) -> Profile:
        """Return a new Profile with updated location."""
        return Profile(
            id=self.id,
            user_id=self.user_id,
            bio=self.bio,
            avatar_url=self.avatar_url,
            cover_photo_url=self.cover_photo_url,
            location=location,
            website=self.website,
            date_of_birth=self.date_of_birth,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    def update_website(self, website: str) -> Profile:
        """Return a new Profile with updated website."""
        return Profile(
            id=self.id,
            user_id=self.user_id,
            bio=self.bio,
            avatar_url=self.avatar_url,
            cover_photo_url=self.cover_photo_url,
            location=self.location,
            website=website,
            date_of_birth=self.date_of_birth,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
