from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from fb.domain.auth.entities import User
from fb.domain.auth.value_objects import Email, HashedPassword
from fb.domain.shared.entity_id import EntityId
from fb.domain.shared.pagination import CursorPage, PageInfo
from fb.infrastructure.database.models.user import UserModel


class SqlAlchemyUserSearchRepository:
    """SQLAlchemy implementation of UserSearchRepository protocol."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search_users(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
    ) -> CursorPage[User]:
        """Search users by display_name or email (case-insensitive, partial match).

        Only returns active users, ordered by display_name ascending.
        """
        search_pattern = f"%{query}%"

        filter_condition = (
            or_(
                UserModel.display_name.ilike(search_pattern),
                UserModel.email.ilike(search_pattern),
            )
            & (UserModel.is_active == True)  # noqa: E712
        )

        # Count total matching rows
        count_stmt = select(func.count()).select_from(UserModel).where(filter_condition)
        count_result = await self._session.execute(count_stmt)
        total_count = count_result.scalar_one()

        # Fetch the page of results
        query_stmt = (
            select(UserModel)
            .where(filter_condition)
            .order_by(UserModel.display_name.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(query_stmt)
        models = result.scalars().all()

        items = tuple(self._to_entity(model) for model in models)

        page_info = PageInfo(
            has_next_page=offset + limit < total_count,
            has_previous_page=offset > 0,
        )

        return CursorPage(
            items=items,
            page_info=page_info,
            total_count=total_count,
        )

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
