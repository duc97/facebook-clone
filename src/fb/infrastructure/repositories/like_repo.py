from __future__ import annotations

from sqlalchemy import select, delete, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from fb.domain.shared.entity_id import EntityId
from fb.domain.post.like import Like
from fb.domain.post.like_repository import LikeRepository
from fb.infrastructure.database.models.like import LikeModel


class SqlAlchemyLikeRepository(LikeRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_post_and_user(self, post_id: EntityId, user_id: EntityId) -> Like | None:
        stmt = select(LikeModel).where(
            and_(LikeModel.post_id == post_id.value, LikeModel.user_id == user_id.value)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return self._to_entity(model)

    async def save(self, like: Like) -> Like:
        model = LikeModel(
            id=like.id.value,
            post_id=like.post_id.value,
            user_id=like.user_id.value,
        )

        # For updates, merge the model
        model = await self._session.merge(model)
        await self._session.flush()

        return self._to_entity(model)

    async def delete(self, like_id: EntityId) -> None:
        stmt = delete(LikeModel).where(LikeModel.id == like_id.value)
        await self._session.execute(stmt)

    async def count_by_post(self, post_id: EntityId) -> int:
        stmt = select(func.count(LikeModel.id)).where(LikeModel.post_id == post_id.value)
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def find_by_post(self, post_id: EntityId, limit: int = 20, offset: int = 0) -> list[Like]:
        stmt = (
            select(LikeModel)
            .where(LikeModel.post_id == post_id.value)
            .order_by(LikeModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._to_entity(model) for model in models]

    def _to_entity(self, model: LikeModel) -> Like:
        return Like(
            id=EntityId.from_str(str(model.id)),
            post_id=EntityId.from_str(str(model.post_id)),
            user_id=EntityId.from_str(str(model.user_id)),
            created_at=model.created_at,
        )