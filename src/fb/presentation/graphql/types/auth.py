from __future__ import annotations

import strawberry


@strawberry.type
class TokenResponse:
    access_token: str
    refresh_token: str
    token_type: str


@strawberry.type
class UserType:
    id: strawberry.ID
    user_name: str
    email: str
    first_name: str
    last_name: str
    display_name: str
    is_active: bool


@strawberry.type
class MessageResponse:
    message: str
    success: bool
