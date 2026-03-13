from __future__ import annotations

from sqlalchemy import select, delete, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from fb.domain.shared.entity_id import EntityId
from fb.domain.post.reaction import Reaction, ReactionType
from fb.domain.post.reaction_repository import ReactionRepository
from fb.infrastructure.database.models.reaction import ReactionModel


class SqlAlchemyReactionRepository(ReactionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_post_and_user(
        self, post_id: EntityId, user_id: EntityId
    ) -> Reaction | None:
        stmt = select(ReactionModel).where(
            and_(
                ReactionModel.post_id == post_id.value,
                ReactionModel.user_id == user_id.value,
            )
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return None
        return self._to_entity(model)

    async def save(self, reaction: Reaction) -> Reaction:
        model = ReactionModel(
            post_id=reaction.post_id.value,
            user_id=reaction.user_id.value,
            reaction_type=reaction.reaction_type.value,
        )
        # Use merge so upsert works
        model.id = reaction.id.value  # type: ignore[assignment]
        model = await self._session.merge(model)
        await self._session.flush()
        return self._to_entity(model)

    async def delete(self, reaction_id: EntityId) -> None:
        stmt = delete(ReactionModel).where(ReactionModel.id == reaction_id.value)
        await self._session.execute(stmt)

    async def find_by_post(
        self, post_id: EntityId, limit: int = 20, offset: int = 0
    ) -> list[Reaction]:
        stmt = (
            select(ReactionModel)
            .where(ReactionModel.post_id == post_id.value)
            .order_by(ReactionModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def count_by_post(self, post_id: EntityId) -> int:
        stmt = select(func.count(ReactionModel.id)).where(
            ReactionModel.post_id == post_id.value
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def count_by_type(self, post_id: EntityId) -> dict[ReactionType, int]:
        stmt = (
            select(ReactionModel.reaction_type, func.count(ReactionModel.id))
            .where(ReactionModel.post_id == post_id.value)
            .group_by(ReactionModel.reaction_type)
        )
        result = await self._session.execute(stmt)
        return {
            ReactionType(row[0]): row[1]
            for row in result.all()
        }

    def _to_entity(self, model: ReactionModel) -> Reaction:
        return Reaction(
            id=EntityId.from_str(str(model.id)),
            post_id=EntityId.from_str(str(model.post_id)),
            user_id=EntityId.from_str(str(model.user_id)),
            reaction_type=ReactionType(model.reaction_type),
            created_at=model.created_at,
        )
