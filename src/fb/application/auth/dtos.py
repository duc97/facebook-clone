from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RegisterInput:
    email: str
    password: str
    display_name: str


@dataclass(frozen=True, slots=True)
class LoginInput:
    email: str
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
    email: str
    display_name: str
    is_active: bool
