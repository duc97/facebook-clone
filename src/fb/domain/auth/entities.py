from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime

from fb.domain.shared.entity_id import EntityId
from fb.domain.auth.value_objects import Email, HashedPassword, UserName


@dataclass(frozen=True, slots=True)
class User:
    """User domain entity."""

    id: EntityId
    user_name: UserName
    email: Email
    hashed_password: HashedPassword
    first_name: str
    last_name: str
    display_name: str
    is_active: bool = True
    date_of_birth: date | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def create(
        cls,
        user_name: str,
        email: str,
        hashed_password: str,
        first_name: str,
        last_name: str,
        date_of_birth: date | None = None,
    ) -> User:
        """Factory method to create a new User."""
        return cls(
            id=EntityId.generate(),
            user_name=UserName(user_name),
            email=Email(email),
            hashed_password=HashedPassword(hashed_password),
            first_name=first_name,
            last_name=last_name,
            display_name=f"{first_name} {last_name}".strip(),
            date_of_birth=date_of_birth,
        )

    def deactivate(self) -> User:
        """Return a new User with is_active=False."""
        return replace(self, is_active=False)

    def change_password(self, new_hashed_password: str) -> User:
        """Return a new User with updated password."""
        return replace(self, hashed_password=HashedPassword(new_hashed_password))

    def update_display_name(self, new_name: str) -> User:
        """Return a new User with updated display name."""
        return replace(self, display_name=new_name)

    def update_profile_fields(
        self,
        first_name: str | None = None,
        last_name: str | None = None,
        date_of_birth: date | None = None,
    ) -> User:
        """Return a new User with updated profile fields."""
        new_first = first_name if first_name is not None else self.first_name
        new_last = last_name if last_name is not None else self.last_name
        new_dob = date_of_birth if date_of_birth is not None else self.date_of_birth
        new_display = f"{new_first} {new_last}".strip()
        return replace(
            self,
            first_name=new_first,
            last_name=new_last,
            date_of_birth=new_dob,
            display_name=new_display,
        )
