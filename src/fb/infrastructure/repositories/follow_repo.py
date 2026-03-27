from __future__ import annotations

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fb.domain.follow.entities import Follow
from fb.domain.shared.entity_id import EntityId
from fb.infrastructure.database.models.follow import FollowModel


class SqlAlchemyFollowRepository:
    """SQLAlchemy implementation of FollowRepository protocol."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, follow: Follow) -> Follow:
        model = FollowModel(
            follower_id=follow.follower_id.value,
            following_id=follow.following_id.value,
        )
        model.id = follow.id.value
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def delete(self, follower_id: EntityId, following_id: EntityId) -> None:
        await self._session.execute(
            delete(FollowModel).where(
                and_(
                    FollowModel.follower_id == follower_id.value,
                    FollowModel.following_id == following_id.value,
                )
            )
        )
        await self._session.flush()

    async def is_following(
        self, follower_id: EntityId, following_id: EntityId
    ) -> bool:
        result = await self._session.execute(
            select(FollowModel.id)
            .where(
                and_(
                    FollowModel.follower_id == follower_id.value,
                    FollowModel.following_id == following_id.value,
                )
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def get_following(
        self, user_id: EntityId, limit: int = 20, offset: int = 0
    ) -> list[EntityId]:
        result = await self._session.execute(
            select(FollowModel.following_id)
            .where(FollowModel.follower_id == user_id.value)
            .order_by(FollowModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [EntityId(row) for row in result.scalars().all()]

    async def get_followers(
        self, user_id: EntityId, limit: int = 20, offset: int = 0
    ) -> list[EntityId]:
        result = await self._session.execute(
            select(FollowModel.follower_id)
            .where(FollowModel.following_id == user_id.value)
            .order_by(FollowModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [EntityId(row) for row in result.scalars().all()]

    async def get_following_count(self, user_id: EntityId) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(FollowModel)
            .where(FollowModel.follower_id == user_id.value)
        )
        return result.scalar_one()

    async def get_followers_count(self, user_id: EntityId) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(FollowModel)
            .where(FollowModel.following_id == user_id.value)
        )
        return result.scalar_one()

    @staticmethod
    def _to_entity(model: FollowModel) -> Follow:
        return Follow(
            id=EntityId(model.id),
            follower_id=EntityId(model.follower_id),
            following_id=EntityId(model.following_id),
            created_at=model.created_at,
        )
