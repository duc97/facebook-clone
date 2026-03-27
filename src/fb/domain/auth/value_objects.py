from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Email:
    """Email value object with validation."""

    value: str

    def __post_init__(self) -> None:
        if not self._is_valid(self.value):
            raise ValueError(f"Invalid email address: {self.value}")

    @staticmethod
    def _is_valid(email: str) -> bool:
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class HashedPassword:
    """Hashed password value object. Never stores plaintext."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("Hashed password cannot be empty")

    def __str__(self) -> str:
        return "***"

    def __repr__(self) -> str:
        return "HashedPassword(***)"


@dataclass(frozen=True, slots=True)
class UserName:
    """Username value object with validation."""

    value: str

    def __post_init__(self) -> None:
        if not self._is_valid(self.value):
            raise ValueError(
                f"Invalid username: {self.value}. "
                "Must be 3-50 chars, alphanumeric/underscore/dot only."
            )

    @staticmethod
    def _is_valid(username: str) -> bool:
        pattern = r"^[a-zA-Z0-9_.]{3,50}$"
        return bool(re.match(pattern, username))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class TokenPair:
    """Access + Refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
