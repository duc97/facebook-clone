from __future__ import annotations

from fb.application.notification.dtos import CreateNotificationInput, NotificationOutput
from fb.application.shared.interfaces import UnitOfWork
from fb.domain.notification.entities import Notification, NotificationType
from fb.domain.notification.repository import NotificationRepository
from fb.domain.shared.entity_id import EntityId


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


class CreateNotificationUseCase:
    def __init__(self, notification_repo: NotificationRepository, uow: UnitOfWork) -> None:
        self._notification_repo = notification_repo
        self._uow = uow

    async def execute(self, input_data: CreateNotificationInput) -> NotificationOutput:
        # Don't notify yourself
        if input_data.user_id == input_data.actor_id:
            return NotificationOutput(
                id="",
                user_id=input_data.user_id,
                actor_id=input_data.actor_id,
                notification_type=input_data.notification_type,
                entity_id=input_data.entity_id,
                entity_type=input_data.entity_type,
                message=input_data.message,
                is_read=False,
                created_at=None,
            )

        notification = Notification.create(
            user_id=EntityId.from_str(input_data.user_id),
            actor_id=EntityId.from_str(input_data.actor_id),
            notification_type=NotificationType(input_data.notification_type),
            entity_id=input_data.entity_id,
            entity_type=input_data.entity_type,
            message=input_data.message,
        )
        saved = await self._notification_repo.add(notification)
        await self._uow.commit()
        return _to_output(saved)
