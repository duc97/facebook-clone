from __future__ import annotations

from fb.application.auth.dtos import LoginInput, TokenOutput
from fb.domain.auth.exceptions import InvalidCredentialsError, UserInactiveError
from fb.domain.auth.repository import UserRepository
from fb.domain.auth.services import PasswordHasher, TokenService


class LoginUseCase:
    """Authenticate user and return token pair."""

    def __init__(
        self,
        user_repo: UserRepository,
        password_hasher: PasswordHasher,
        token_service: TokenService,
    ) -> None:
        self._user_repo = user_repo
        self._password_hasher = password_hasher
        self._token_service = token_service

    async def execute(self, input_data: LoginInput) -> TokenOutput:
        # Find user by email
        user = await self._user_repo.find_by_email(input_data.email)
        if user is None:
            raise InvalidCredentialsError()

        # Check if user is active
        if not user.is_active:
            raise UserInactiveError()

        # Verify password
        if not self._password_hasher.verify(
            input_data.password, user.hashed_password.value
        ):
            raise InvalidCredentialsError()

        # Generate tokens
        access_token = self._token_service.create_access_token(
            user_id=str(user.id),
            email=str(user.email),
        )
        refresh_token = self._token_service.create_refresh_token(
            user_id=str(user.id),
        )

        return TokenOutput(
            access_token=access_token,
            refresh_token=refresh_token,
        )
