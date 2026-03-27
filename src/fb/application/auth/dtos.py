from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class RegisterInput:
    user_name: str
    email: str
    first_name: str
    last_name: str
    password: str
    birthday: date | None = None


@dataclass(frozen=True, slots=True)
class LoginInput:
    user_name: str
    password: str


@dataclass(frozen=True, slots=True)
class TokenOutput:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@dataclass(frozen=True, slots=True)
class RefreshTokenInput:
    refresh_token: str


@dataclass(frozen=True, slots=True)
class LogoutInput:
    access_token: str
    refresh_token: str


@dataclass(frozen=True, slots=True)
class UserOutput:
    id: str
    user_name: str
    email: str
    first_name: str
    last_name: str
    display_name: str
    is_active: bool


@dataclass(frozen=True, slots=True)
class EditUserInput:
    user_id: str
    first_name: str | None = None
    last_name: str | None = None
    birthday: date | None = None
    password: str | None = None
