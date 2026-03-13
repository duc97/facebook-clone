from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fb.domain.shared.entity_id import EntityId
from fb.domain.auth.value_objects import Email, HashedPassword


@dataclass(frozen=True, slots=True)
class User:
    """User domain entity."""

    id: EntityId
    email: Email
    hashed_password: HashedPassword
    display_name: str
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def create(
        cls,
        email: str,
        hashed_password: str,
        display_name: str,
    ) -> User:
        """Factory method to create a new User."""
        return cls(
            id=EntityId.generate(),
            email=Email(email),
            hashed_password=HashedPassword(hashed_password),
            display_name=display_name,
        )

    def deactivate(self) -> User:
        """Return a new User with is_active=False."""
        return User(
            id=self.id,
            email=self.email,
            hashed_password=self.hashed_password,
            display_name=self.display_name,
            is_active=False,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    def change_password(self, new_hashed_password: str) -> User:
        """Return a new User with updated password."""
        return User(
            id=self.id,
            email=self.email,
            hashed_password=HashedPassword(new_hashed_password),
            display_name=self.display_name,
            is_active=self.is_active,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    def update_display_name(self, new_name: str) -> User:
        """Return a new User with updated display name."""
        return User(
            id=self.id,
            email=self.email,
            hashed_password=self.hashed_password,
            display_name=new_name,
            is_active=self.is_active,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
