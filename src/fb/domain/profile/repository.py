from __future__ import annotations

from typing import Protocol, runtime_checkable

from fb.domain.profile.entities import Profile
from fb.domain.shared.entity_id import EntityId


@runtime_checkable
class ProfileRepository(Protocol):
    """Protocol for Profile persistence."""

    async def find_by_user_id(self, user_id: EntityId) -> Profile | None:
        ...

    async def save(self, profile: Profile) -> Profile:
        ...

    async def update(self, profile: Profile) -> Profile:
        ...

    async def exists_by_user_id(self, user_id: EntityId) -> bool:
        ...
