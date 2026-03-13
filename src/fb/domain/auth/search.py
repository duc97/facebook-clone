from __future__ import annotations

from typing import Protocol, runtime_checkable

from fb.domain.auth.entities import User
from fb.domain.shared.pagination import CursorPage


@runtime_checkable
class UserSearchRepository(Protocol):
    """Protocol for searching users by display_name or email."""

    async def search_users(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
    ) -> CursorPage[User]:
        """Search users by display_name or email (case-insensitive, partial match)."""
        ...
