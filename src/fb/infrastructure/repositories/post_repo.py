from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fb.domain.post.entities import Post
from fb.domain.shared.entity_id import EntityId
from fb.infrastructure.database.models.post import PostModel


class SqlAlchemyPostRepository:
    """SQLAlchemy implementation of PostRepository protocol."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, post_id: EntityId) -> Post | None:
        result = await self._session.execute(
            select(PostModel).where(PostModel.id == post_id.value)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def save(self, post: Post) -> Post:
        model = PostModel(
            author_id=post.author_id.value,
            content=post.content,
        )
        model.id = post.id.value
        model.media_urls = list(post.media_urls)
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def update(self, post: Post) -> Post:
        result = await self._session.execute(
            select(PostModel).where(PostModel.id == post.id.value)
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise ValueError(f"Post {post.id} not found")
        model.content = post.content
        model.media_urls = list(post.media_urls)
        model.like_count = post.like_count
        model.comment_count = post.comment_count
        model.is_published = post.is_published
        await self._session.flush()
        return self._to_entity(model)

    async def delete(self, post_id: EntityId) -> None:
        result = await self._session.execute(
            select(PostModel).where(PostModel.id == post_id.value)
        )
        model = result.scalar_one_or_none()
        if model is not None:
            model.is_published = False
            await self._session.flush()

    async def find_by_author(
        self, author_id: EntityId, limit: int = 20, offset: int = 0
    ) -> list[Post]:
        result = await self._session.execute(
            select(PostModel)
            .where(
                PostModel.author_id == author_id.value,
                PostModel.is_published == True,  # noqa: E712
            )
            .order_by(PostModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def count_by_author(self, author_id: EntityId) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(PostModel)
            .where(
                PostModel.author_id == author_id.value,
                PostModel.is_published == True,  # noqa: E712
            )
        )
        return result.scalar_one()

    @staticmethod
    def _to_entity(model: PostModel) -> Post:
        return Post(
            id=EntityId(model.id),
            author_id=EntityId(model.author_id),
            content=model.content,
            media_urls=tuple(model.media_urls or []),
            like_count=model.like_count,
            comment_count=model.comment_count,
            is_published=model.is_published,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
