from __future__ import annotations

from fb.application.auth.dtos import RefreshTokenInput, TokenOutput
from fb.domain.auth.exceptions import (
    InvalidTokenError,
    TokenBlacklistedError,
    UserNotFoundError,
)
from fb.domain.auth.repository import UserRepository
from fb.domain.auth.services import TokenBlacklist, TokenService
from fb.domain.shared.entity_id import EntityId


class RefreshTokenUseCase:
    """Refresh access token using a valid refresh token."""

    def __init__(
        self,
        token_service: TokenService,
        token_blacklist: TokenBlacklist,
        user_repo: UserRepository,
    ) -> None:
        self._token_service = token_service
        self._token_blacklist = token_blacklist
        self._user_repo = user_repo

    async def execute(self, input_data: RefreshTokenInput) -> TokenOutput:
        # Check if token is blacklisted
        if await self._token_blacklist.is_blacklisted(input_data.refresh_token):
            raise TokenBlacklistedError()

        # Decode refresh token
        try:
            payload = self._token_service.decode_refresh_token(
                input_data.refresh_token
            )
        except Exception:
            raise InvalidTokenError("Invalid refresh token")

        user_id = payload.get("sub")
        if not user_id:
            raise InvalidTokenError("Invalid refresh token payload")

        # Look up user to ensure they still exist and are active
        user = await self._user_repo.find_by_id(EntityId.from_str(user_id))
        if user is None:
            raise UserNotFoundError(user_id)

        if not user.is_active:
            raise InvalidTokenError("User account is deactivated")

        # Generate new token pair
        access_token = self._token_service.create_access_token(
            user_id=str(user.id),
            email=str(user.email),
        )
        new_refresh_token = self._token_service.create_refresh_token(
            user_id=str(user.id),
        )

        return TokenOutput(
            access_token=access_token,
            refresh_token=new_refresh_token,
        )
