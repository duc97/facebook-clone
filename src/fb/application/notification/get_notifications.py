from __future__ import annotations

from fb.application.notification.dtos import NotificationOutput, NotificationsOutput
from fb.domain.notification.repository import NotificationRepository
from fb.domain.shared.entity_id import EntityId
from fb.domain.notification.entities import Notification


def _to_output(notification: Notification) -> NotificationOutput:
    return NotificationOutput(
        id=str(notification.id),
        user_id=str(notification.user_id),
        actor_id=str(notification.actor_id),
        notification_type=notification.notification_type.value,
        entity_id=notification.entity_id,
        entity_type=notification.entity_type,
        message=notification.message,
        is_read=notification.is_read,
        created_at=notification.created_at.isoformat() if notification.created_at else None,
    )


class GetNotificationsUseCase:
    def __init__(self, notification_repo: NotificationRepository) -> None:
        self._notification_repo = notification_repo

    async def execute(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
        unread_only: bool = False,
    ) -> NotificationsOutput:
        uid = EntityId.from_str(user_id)
        notifications = await self._notification_repo.get_by_user(uid, limit, offset, unread_only)
        unread_count = await self._notification_repo.count_unread(uid)
        return NotificationsOutput(
            notifications=[_to_output(n) for n in notifications],
            unread_count=unread_count,
            total_count=len(notifications),
        )
