from __future__ import annotations

from fb.application.auth.dtos import EditUserInput, UserOutput
from fb.application.shared.interfaces import UnitOfWork
from fb.domain.auth.exceptions import UserNotFoundError
from fb.domain.auth.repository import UserRepository
from fb.domain.auth.services import PasswordHasher
from fb.domain.shared.entity_id import EntityId


class EditUserUseCase:
    """Edit user profile fields (first_name, last_name, birthday, password)."""

    def __init__(
        self,
        user_repo: UserRepository,
        password_hasher: PasswordHasher,
        uow: UnitOfWork,
    ) -> None:
        self._user_repo = user_repo
        self._password_hasher = password_hasher
        self._uow = uow

    async def execute(self, input_data: EditUserInput) -> UserOutput:
        async with self._uow:
            user_id = EntityId.from_str(input_data.user_id)
            user = await self._user_repo.find_by_id(user_id)
            if user is None:
                raise UserNotFoundError(input_data.user_id)

            # Update profile fields
            user = user.update_profile_fields(
                first_name=input_data.first_name,
                last_name=input_data.last_name,
                date_of_birth=input_data.birthday,
            )

            # Update password if provided
            if input_data.password is not None:
                hashed = self._password_hasher.hash(input_data.password)
                user = user.change_password(hashed)

            updated = await self._user_repo.update(user)
            await self._uow.commit()

            return UserOutput(
                id=str(updated.id),
                user_name=str(updated.user_name),
                email=str(updated.email),
                first_name=updated.first_name,
                last_name=updated.last_name,
                display_name=updated.display_name,
                is_active=updated.is_active,
            )
