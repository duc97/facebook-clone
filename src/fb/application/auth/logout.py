from __future__ import annotations

from fb.application.auth.dtos import LogoutInput
from fb.domain.auth.services import TokenBlacklist


class LogoutUseCase:
    """Blacklist both access and refresh tokens."""

    # Default expiry: 7 days in seconds (matches refresh token lifetime)
    _REFRESH_EXPIRY_SECONDS = 7 * 24 * 60 * 60
    # Default expiry: 15 minutes in seconds (matches access token lifetime)
    _ACCESS_EXPIRY_SECONDS = 15 * 60

    def __init__(self, token_blacklist: TokenBlacklist) -> None:
        self._token_blacklist = token_blacklist

    async def execute(self, input_data: LogoutInput) -> None:
        await self._token_blacklist.blacklist(
            input_data.access_token,
            expires_in=self._ACCESS_EXPIRY_SECONDS,
        )
        await self._token_blacklist.blacklist(
            input_data.refresh_token,
            expires_in=self._REFRESH_EXPIRY_SECONDS,
        )
