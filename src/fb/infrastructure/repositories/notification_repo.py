from __future__ import annotations

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from fb.domain.notification.entities import Notification, NotificationType
from fb.domain.notification.repository import NotificationRepository
from fb.domain.shared.entity_id import EntityId
from fb.infrastructure.database.models.notification import NotificationModel


class SqlAlchemyNotificationRepository(NotificationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, notification: Notification) -> Notification:
        model = NotificationModel(
            id=notification.id.value,
            user_id=notification.user_id.value,
            actor_id=notification.actor_id.value,
            notification_type=notification.notification_type.value,
            entity_id=notification.entity_id,
            entity_type=notification.entity_type,
            message=notification.message,
        )
        model = await self._session.merge(model)
        await self._session.flush()
        return self._to_entity(model)

    async def find_by_id(self, notification_id: EntityId) -> Notification | None:
        stmt = select(NotificationModel).where(
            NotificationModel.id == notification_id.value
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_entity(model)

    async def get_by_user(
        self,
        user_id: EntityId,
        limit: int = 20,
        offset: int = 0,
        unread_only: bool = False,
    ) -> list[Notification]:
        # Performance: user_id filter applied first to align with
        # ix_notifications_user_read_created index (migration 006): (user_id, is_read, created_at).
        stmt = select(NotificationModel).where(
            NotificationModel.user_id == user_id.value
        )
        if unread_only:
            # is_read filter as second predicate matches the composite index column order.
            stmt = stmt.where(NotificationModel.is_read.is_(False))
        stmt = (
            stmt.order_by(NotificationModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def count_unread(self, user_id: EntityId) -> int:
        # Performance: uses ix_notifications_user_read_created composite index (migration 006)
        # covering (user_id, is_read, created_at) — enables Index Only Scan for this count query.
        stmt = (
            select(func.count(NotificationModel.id))
            .where(NotificationModel.user_id == user_id.value)
            .where(NotificationModel.is_read.is_(False))
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def mark_read(self, notification_id: EntityId) -> None:
        stmt = (
            update(NotificationModel)
            .where(NotificationModel.id == notification_id.value)
            .values(is_read=True)
        )
        await self._session.execute(stmt)

    async def mark_all_read(self, user_id: EntityId) -> None:
        stmt = (
            update(NotificationModel)
            .where(NotificationModel.user_id == user_id.value)
            .where(NotificationModel.is_read.is_(False))
            .values(is_read=True)
        )
        await self._session.execute(stmt)

    def _to_entity(self, model: NotificationModel) -> Notification:
        return Notification(
            id=EntityId.from_str(str(model.id)),
            user_id=EntityId.from_str(str(model.user_id)),
            actor_id=EntityId.from_str(str(model.actor_id)),
            notification_type=NotificationType(model.notification_type),
            entity_id=model.entity_id,
            entity_type=model.entity_type,
            message=model.message,
            is_read=model.is_read,
            created_at=model.created_at,
        )
