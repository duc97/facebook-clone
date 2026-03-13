from __future__ import annotations

from typing import Protocol, runtime_checkable

from fb.domain.notification.entities import Notification
from fb.domain.shared.entity_id import EntityId


@runtime_checkable
class NotificationRepository(Protocol):
    async def add(self, notification: Notification) -> Notification: ...
    async def find_by_id(self, notification_id: EntityId) -> Notification | None: ...
    async def get_by_user(
        self,
        user_id: EntityId,
        limit: int = 20,
        offset: int = 0,
        unread_only: bool = False,
    ) -> list[Notification]: ...
    async def count_unread(self, user_id: EntityId) -> int: ...
    async def mark_read(self, notification_id: EntityId) -> None: ...
    async def mark_all_read(self, user_id: EntityId) -> None: ...
