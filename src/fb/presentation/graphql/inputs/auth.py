from __future__ import annotations

import strawberry


@strawberry.input
class RegisterInput:
    email: str
    password: str
    display_name: str


@strawberry.input
class LoginInput:
    email: str
    password: str


@strawberry.input
class RefreshTokenInput:
    refresh_token: str
