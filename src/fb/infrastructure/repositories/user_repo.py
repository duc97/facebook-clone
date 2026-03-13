from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fb.domain.auth.entities import User
from fb.domain.auth.value_objects import Email, HashedPassword
from fb.domain.shared.entity_id import EntityId
from fb.infrastructure.database.models.user import UserModel


class SqlAlchemyUserRepository:
    """SQLAlchemy implementation of UserRepository protocol."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, user_id: EntityId) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user_id.value)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == email)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def save(self, user: User) -> User:
        model = UserModel(
            email=str(user.email),
            hashed_password=user.hashed_password.value,
            display_name=user.display_name,
        )
        # Override the auto-generated id with our domain id
        model.id = user.id.value
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def update(self, user: User) -> User:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user.id.value)
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise ValueError(f"User {user.id} not found")
        model.email = str(user.email)
        model.hashed_password = user.hashed_password.value
        model.display_name = user.display_name
        model.is_active = user.is_active
        await self._session.flush()
        return self._to_entity(model)

    async def exists_by_email(self, email: str) -> bool:
        result = await self._session.execute(
            select(UserModel.id).where(UserModel.email == email).limit(1)
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    def _to_entity(model: UserModel) -> User:
        return User(
            id=EntityId(model.id),
            email=Email(model.email),
            hashed_password=HashedPassword(model.hashed_password),
            display_name=model.display_name,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
