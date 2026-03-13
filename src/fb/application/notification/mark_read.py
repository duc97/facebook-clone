from __future__ import annotations

from fb.application.shared.interfaces import UnitOfWork
from fb.domain.notification.exceptions import NotificationNotFoundError
from fb.domain.notification.repository import NotificationRepository
from fb.domain.shared.entity_id import EntityId


class MarkNotificationReadUseCase:
    def __init__(self, notification_repo: NotificationRepository, uow: UnitOfWork) -> None:
        self._notification_repo = notification_repo
        self._uow = uow

    async def execute(self, notification_id: str, user_id: str) -> None:
        nid = EntityId.from_str(notification_id)
        notification = await self._notification_repo.find_by_id(nid)
        if notification is None:
            raise NotificationNotFoundError()
        # Only the owner can mark as read
        if str(notification.user_id) != user_id:
            raise NotificationNotFoundError()  # hide existence from non-owners
        await self._notification_repo.mark_read(nid)
        await self._uow.commit()


class MarkAllReadUseCase:
    def __init__(self, notification_repo: NotificationRepository, uow: UnitOfWork) -> None:
        self._notification_repo = notification_repo
        self._uow = uow

    async def execute(self, user_id: str) -> None:
        uid = EntityId.from_str(user_id)
        await self._notification_repo.mark_all_read(uid)
        await self._uow.commit()
