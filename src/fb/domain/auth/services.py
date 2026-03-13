from __future__ import annotations

from typing import Protocol, runtime_checkable

from fb.domain.shared.entity_id import EntityId


@runtime_checkable
class PasswordHasher(Protocol):
    """Protocol for password hashing."""

    def hash(self, password: str) -> str:
        ...

    def verify(self, password: str, hashed: str) -> bool:
        ...


@runtime_checkable
class TokenService(Protocol):
    """Protocol for JWT token management."""

    def create_access_token(self, user_id: str, email: str) -> str:
        ...

    def create_refresh_token(self, user_id: str) -> str:
        ...

    def decode_access_token(self, token: str) -> dict[str, str]:
        """Returns dict with 'sub' (user_id) and 'email'."""
        ...

    def decode_refresh_token(self, token: str) -> dict[str, str]:
        """Returns dict with 'sub' (user_id)."""
        ...


@runtime_checkable
class TokenBlacklist(Protocol):
    """Protocol for token blacklisting (logout)."""

    async def blacklist(self, token: str, expires_in: int) -> None:
        ...

    async def is_blacklisted(self, token: str) -> bool:
        ...
