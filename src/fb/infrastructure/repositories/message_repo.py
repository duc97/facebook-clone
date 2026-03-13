from __future__ import annotations

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from fb.domain.chat.entities import Conversation, Message
from fb.domain.chat.repository import MessageRepository
from fb.domain.shared.entity_id import EntityId
from fb.domain.shared.pagination import CursorPage, PageInfo, decode_cursor, encode_cursor
from fb.infrastructure.database.models.message import MessageModel


class SqlAlchemyMessageRepository(MessageRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, message: Message) -> Message:
        model = MessageModel(
            id=message.id.value,
            sender_id=message.sender_id.value,
            receiver_id=message.receiver_id.value,
            content=message.content,
        )
        model = await self._session.merge(model)
        await self._session.flush()
        return self._to_entity(model)

    async def find_by_id(self, message_id: EntityId) -> Message | None:
        stmt = select(MessageModel).where(MessageModel.id == message_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_entity(model)

    async def mark_seen(self, message_id: EntityId) -> None:
        stmt = (
            update(MessageModel)
            .where(MessageModel.id == message_id.value)
            .values(is_seen=True)
        )
        await self._session.execute(stmt)

    async def mark_conversation_seen(
        self, user_id: EntityId, other_user_id: EntityId
    ) -> None:
        stmt = (
            update(MessageModel)
            .where(
                and_(
                    MessageModel.sender_id == other_user_id.value,
                    MessageModel.receiver_id == user_id.value,
                    MessageModel.is_seen.is_(False),
                )
            )
            .values(is_seen=True)
        )
        await self._session.execute(stmt)

    async def get_conversation_messages(
        self,
        user_id: EntityId,
        other_user_id: EntityId,
        first: int = 20,
        after_cursor: str | None = None,
    ) -> CursorPage[Message]:
        conversation_filter = or_(
            and_(
                MessageModel.sender_id == user_id.value,
                MessageModel.receiver_id == other_user_id.value,
            ),
            and_(
                MessageModel.sender_id == other_user_id.value,
                MessageModel.receiver_id == user_id.value,
            ),
        )

        base = select(MessageModel).where(conversation_filter)

        if after_cursor:
            cursor_time, cursor_id = decode_cursor(after_cursor)
            base = base.where(
                or_(
                    MessageModel.created_at < cursor_time,
                    and_(
                        MessageModel.created_at == cursor_time,
                        MessageModel.id < cursor_id,
                    ),
                )
            )

        stmt = (
            base.order_by(MessageModel.created_at.desc(), MessageModel.id.desc())
            .limit(first + 1)
        )
        result = await self._session.execute(stmt)
        models = list(result.scalars().all())

        has_next = len(models) > first
        items = [self._to_entity(m) for m in models[:first]]

        count_stmt = select(func.count(MessageModel.id)).where(conversation_filter)
        total = (await self._session.execute(count_stmt)).scalar() or 0

        start_cursor = (
            encode_cursor(items[0].created_at, str(items[0].id))
            if items and items[0].created_at
            else None
        )
        end_cursor = (
            encode_cursor(items[-1].created_at, str(items[-1].id))
            if items and items[-1].created_at
            else None
        )

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

    async def get_conversations(
        self, user_id: EntityId, limit: int = 20, offset: int = 0
    ) -> list[Conversation]:
        """Get conversations using a single optimized query — no N+1.

        Replaces the previous loop (N queries for N partners) with a single
        raw SQL query using DISTINCT ON to find the latest message per
        conversation partner, and a GROUP BY subquery for unread counts.

        Performance: uses ix_messages_receiver_seen index (migration 006) for
        the unread_counts CTE and ix_message_conversation for message lookups.
        """
        from sqlalchemy import text

        # Use a single raw SQL query with CTEs to avoid the N+1 loop:
        #   1. last_msgs  — DISTINCT ON picks the latest message per partner
        #   2. unread_counts — aggregates unseen messages per sender
        # Both CTEs are joined in a single SELECT, ordered by recency.
        raw_sql = text("""
            WITH last_msgs AS (
                SELECT DISTINCT ON (
                    CASE
                        WHEN sender_id = :uid THEN receiver_id
                        ELSE sender_id
                    END
                )
                    id,
                    sender_id,
                    receiver_id,
                    content,
                    is_seen,
                    created_at,
                    CASE
                        WHEN sender_id = :uid THEN receiver_id
                        ELSE sender_id
                    END AS partner_id
                FROM messages
                WHERE sender_id = :uid OR receiver_id = :uid
                ORDER BY
                    CASE
                        WHEN sender_id = :uid THEN receiver_id
                        ELSE sender_id
                    END,
                    created_at DESC
            ),
            unread_counts AS (
                SELECT sender_id AS partner_id, COUNT(*) AS cnt
                FROM messages
                WHERE receiver_id = :uid AND is_seen = false
                GROUP BY sender_id
            )
            SELECT
                lm.partner_id,
                lm.id          AS msg_id,
                lm.sender_id,
                lm.receiver_id,
                lm.content,
                lm.is_seen,
                lm.created_at,
                COALESCE(uc.cnt, 0) AS unread_count
            FROM last_msgs lm
            LEFT JOIN unread_counts uc ON uc.partner_id = lm.partner_id
            ORDER BY lm.created_at DESC
            LIMIT :limit OFFSET :offset
        """)

        result = await self._session.execute(
            raw_sql, {"uid": user_id.value, "limit": limit, "offset": offset}
        )
        rows = result.fetchall()

        conversations: list[Conversation] = []
        for row in rows:
            last_message = Message(
                id=EntityId.from_str(str(row.msg_id)),
                sender_id=EntityId.from_str(str(row.sender_id)),
                receiver_id=EntityId.from_str(str(row.receiver_id)),
                content=row.content,
                is_seen=row.is_seen,
                created_at=row.created_at,
            )
            conversations.append(
                Conversation(
                    user_id=user_id,
                    other_user_id=EntityId.from_str(str(row.partner_id)),
                    last_message=last_message,
                    unread_count=int(row.unread_count),
                )
            )
        return conversations

    async def get_unread_count(self, user_id: EntityId) -> int:
        stmt = (
            select(func.count(MessageModel.id))
            .where(
                and_(
                    MessageModel.receiver_id == user_id.value,
                    MessageModel.is_seen.is_(False),
                )
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    def _to_entity(self, model: MessageModel) -> Message:
        return Message(
            id=EntityId.from_str(str(model.id)),
            sender_id=EntityId.from_str(str(model.sender_id)),
            receiver_id=EntityId.from_str(str(model.receiver_id)),
            content=model.content,
            is_seen=model.is_seen,
            created_at=model.created_at,
        )
