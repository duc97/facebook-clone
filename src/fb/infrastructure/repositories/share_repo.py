from __future__ import annotations

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from fb.domain.shared.entity_id import EntityId
from fb.domain.post.share import Share
from fb.domain.post.share_repository import ShareRepository
from fb.infrastructure.database.models.share import ShareModel


class SqlAlchemyShareRepository(ShareRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, share_id: EntityId) -> Share | None:
        stmt = select(ShareModel).where(ShareModel.id == share_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return None
        return self._to_entity(model)

    async def save(self, share: Share) -> Share:
        model = ShareModel(
            post_id=share.post_id.value,
            user_id=share.user_id.value,
            content=share.content,
        )
        model.id = share.id.value  # type: ignore[assignment]
        model = await self._session.merge(model)
        await self._session.flush()
        return self._to_entity(model)

    async def delete(self, share_id: EntityId) -> None:
        stmt = delete(ShareModel).where(ShareModel.id == share_id.value)
        await self._session.execute(stmt)

    async def find_by_post(
        self, post_id: EntityId, limit: int = 20, offset: int = 0
    ) -> list[Share]:
        stmt = (
            select(ShareModel)
            .where(ShareModel.post_id == post_id.value)
            .order_by(ShareModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def count_by_post(self, post_id: EntityId) -> int:
        stmt = select(func.count(ShareModel.id)).where(
            ShareModel.post_id == post_id.value
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    def _to_entity(self, model: ShareModel) -> Share:
        return Share(
            id=EntityId.from_str(str(model.id)),
            post_id=EntityId.from_str(str(model.post_id)),
            user_id=EntityId.from_str(str(model.user_id)),
            content=model.content,
            created_at=model.created_at,
        )
