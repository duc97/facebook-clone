from __future__ import annotations

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from fb.domain.shared.entity_id import EntityId
from fb.domain.post.comment import Comment
from fb.domain.post.comment_repository import CommentRepository
from fb.infrastructure.database.models.comment import CommentModel


class SqlAlchemyCommentRepository(CommentRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, comment_id: EntityId) -> Comment | None:
        stmt = select(CommentModel).where(CommentModel.id == comment_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return self._to_entity(model)

    async def save(self, comment: Comment) -> Comment:
        model = CommentModel(
            id=comment.id.value,
            post_id=comment.post_id.value,
            author_id=comment.author_id.value,
            content=comment.content,
        )

        # For updates, merge the model
        model = await self._session.merge(model)
        await self._session.flush()

        return self._to_entity(model)

    async def delete(self, comment_id: EntityId) -> None:
        stmt = delete(CommentModel).where(CommentModel.id == comment_id.value)
        await self._session.execute(stmt)

    async def find_by_post(self, post_id: EntityId, limit: int = 20, offset: int = 0) -> list[Comment]:
        stmt = (
            select(CommentModel)
            .where(CommentModel.post_id == post_id.value)
            .order_by(CommentModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._to_entity(model) for model in models]

    async def count_by_post(self, post_id: EntityId) -> int:
        stmt = select(func.count(CommentModel.id)).where(CommentModel.post_id == post_id.value)
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    def _to_entity(self, model: CommentModel) -> Comment:
        return Comment(
            id=EntityId.from_str(str(model.id)),
            post_id=EntityId.from_str(str(model.post_id)),
            author_id=EntityId.from_str(str(model.author_id)),
            content=model.content,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )