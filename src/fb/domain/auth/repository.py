from __future__ import annotations

from typing import Protocol, runtime_checkable

from fb.domain.auth.entities import User
from fb.domain.shared.entity_id import EntityId


@runtime_checkable
class UserRepository(Protocol):
    """Protocol for User persistence."""

    async def find_by_id(self, user_id: EntityId) -> User | None:
        ...

    async def find_by_email(self, email: str) -> User | None:
        ...

    async def find_by_user_name(self, user_name: str) -> User | None:
        ...

    async def save(self, user: User) -> User:
        ...

    async def update(self, user: User) -> User:
        ...

    async def exists_by_email(self, email: str) -> bool:
        ...

    async def exists_by_user_name(self, user_name: str) -> bool:
        ...
