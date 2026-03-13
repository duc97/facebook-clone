from __future__ import annotations

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from fb.domain.post.entities import Post
from fb.domain.post.feed_repository import FeedRepository
from fb.domain.shared.entity_id import EntityId
from fb.domain.shared.pagination import CursorPage, PageInfo, decode_cursor, encode_cursor
from fb.infrastructure.database.models.post import PostModel


class SqlAlchemyFeedRepository:
    """SqlAlchemy implementation of FeedRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_feed_post_ids(
        self, user_id: EntityId, friend_ids: list[EntityId], limit: int = 20, offset: int = 0
    ) -> list[EntityId]:
        """Get post IDs for user's feed (user + friends posts).

        Performance: uses ix_posts_published_author_created index (migration 006)
        EXPLAIN ANALYZE: should show Index Scan on posts using ix_posts_published_author_created
        """
        # Create list of all author IDs (user + friends)
        author_ids = [user_id] + friend_ids

        # Performance: uses ix_posts_published_author_created index (migration 006)
        # EXPLAIN ANALYZE: should show Index Scan on posts
        # UUID values passed directly to keep PostgreSQL index alignment (no string cast).
        stmt = (
            select(PostModel.id)
            .where(
                and_(
                    PostModel.author_id.in_([aid.value for aid in author_ids]),
                    PostModel.is_published == True,  # noqa: E712
                )
            )
            .order_by(PostModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self._session.execute(stmt)
        post_ids = result.scalars().all()

        return [EntityId.from_str(str(pid)) for pid in post_ids]

    async def get_feed_posts(self, post_ids: list[EntityId]) -> list[Post]:
        """Get posts by their IDs in a single IN-clause query — no N+1.

        Performance: single query; UUID values passed directly to keep index alignment.
        """
        if not post_ids:
            return []

        # Single query — no N+1; all IDs fetched in one round-trip.
        stmt = select(PostModel).where(
            PostModel.id.in_([pid.value for pid in post_ids])
        )

        result = await self._session.execute(stmt)
        post_models = result.scalars().all()

        return [self._to_entity(model) for model in post_models]

    async def get_feed_total_count(
        self, user_id: EntityId, friend_ids: list[EntityId]
    ) -> int:
        """Get total count of posts available in user's feed.

        Performance: uses ix_posts_published_author_created index (migration 006)
        EXPLAIN ANALYZE: should show Index Scan on posts
        """
        # Create list of all author IDs (user + friends)
        author_ids = [user_id] + friend_ids

        # UUID values passed directly to keep PostgreSQL index alignment (no string cast).
        stmt = select(func.count(PostModel.id)).where(
            and_(
                PostModel.author_id.in_([aid.value for aid in author_ids]),
                PostModel.is_published == True,  # noqa: E712
            )
        )

        result = await self._session.execute(stmt)
        count = result.scalar()

        return count or 0

    async def get_feed_posts_cursor(
        self, user_id: EntityId, friend_ids: list[EntityId],
        first: int = 20, after_cursor: str | None = None
    ) -> CursorPage[Post]:
        """Get feed posts using cursor-based pagination.

        Performance: uses ix_posts_published_author_created index (migration 006)
        EXPLAIN ANALYZE: should show Index Scan on posts using ix_posts_published_author_created
        """
        author_ids = [user_id] + friend_ids

        # UUID values passed directly to keep PostgreSQL index alignment (no string cast).
        base = select(PostModel).where(
            and_(
                PostModel.author_id.in_([aid.value for aid in author_ids]),
                PostModel.is_published == True,  # noqa: E712
            )
        )

        if after_cursor:
            cursor_time, cursor_id = decode_cursor(after_cursor)
            base = base.where(
                or_(
                    PostModel.created_at < cursor_time,
                    and_(PostModel.created_at == cursor_time, PostModel.id < cursor_id)
                )
            )

        stmt = base.order_by(PostModel.created_at.desc(), PostModel.id.desc()).limit(first + 1)
        result = await self._session.execute(stmt)
        models = list(result.scalars().all())

        has_next = len(models) > first
        items = [self._to_entity(m) for m in models[:first]]

        # UUID values passed directly to keep PostgreSQL index alignment (no string cast).
        count_stmt = select(func.count(PostModel.id)).where(
            and_(
                PostModel.author_id.in_([aid.value for aid in author_ids]),
                PostModel.is_published == True,  # noqa: E712
            )
        )
        total = (await self._session.execute(count_stmt)).scalar() or 0

        start_cursor = encode_cursor(items[0].created_at, str(items[0].id)) if items else None
        end_cursor = encode_cursor(items[-1].created_at, str(items[-1].id)) if items else None

        return CursorPage(
            items=tuple(items),
            page_info=PageInfo(
                has_next_page=has_next,
                has_previous_page=after_cursor is not None,
                start_cursor=start_cursor,
                end_cursor=end_cursor,
            ),
            total_count=total,
        )

    @staticmethod
    def _to_entity(model: PostModel) -> Post:
        """Convert PostModel to Post entity."""
        return Post(
            id=EntityId.from_str(str(model.id)),
            author_id=EntityId.from_str(str(model.author_id)),
            content=model.content,
            media_urls=tuple(model.media_urls or []),
            like_count=model.like_count,
            comment_count=model.comment_count,
            is_published=model.is_published,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
