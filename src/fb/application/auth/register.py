from __future__ import annotations

from fb.application.auth.dtos import RegisterInput, TokenOutput
from fb.application.shared.interfaces import UnitOfWork
from fb.domain.auth.entities import User
from fb.domain.auth.exceptions import EmailAlreadyExistsError
from fb.domain.auth.repository import UserRepository
from fb.domain.auth.services import PasswordHasher, TokenService


class RegisterUseCase:
    """Register a new user and return token pair."""

    def __init__(
        self,
        user_repo: UserRepository,
        password_hasher: PasswordHasher,
        token_service: TokenService,
        uow: UnitOfWork,
    ) -> None:
        self._user_repo = user_repo
        self._password_hasher = password_hasher
        self._token_service = token_service
        self._uow = uow

    async def execute(self, input_data: RegisterInput) -> TokenOutput:
        async with self._uow:
            # Check if email already exists
            if await self._user_repo.exists_by_email(input_data.email):
                raise EmailAlreadyExistsError(input_data.email)

            # Hash password and create user
            hashed = self._password_hasher.hash(input_data.password)
            user = User.create(
                email=input_data.email,
                hashed_password=hashed,
                display_name=input_data.display_name,
            )

            # Persist user
            saved_user = await self._user_repo.save(user)
            await self._uow.commit()

            # Generate tokens
            access_token = self._token_service.create_access_token(
                user_id=str(saved_user.id),
                email=str(saved_user.email),
            )
            refresh_token = self._token_service.create_refresh_token(
                user_id=str(saved_user.id),
            )

            return TokenOutput(
                access_token=access_token,
                refresh_token=refresh_token,
            )
