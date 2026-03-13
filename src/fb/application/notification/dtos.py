from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NotificationOutput:
    id: str
    user_id: str
    actor_id: str
    notification_type: str
    entity_id: str
    entity_type: str
    message: str
    is_read: bool
    created_at: str | None


@dataclass(frozen=True)
class CreateNotificationInput:
    user_id: str
    actor_id: str
    notification_type: str  # must match NotificationType enum value
    entity_id: str
    entity_type: str
    message: str


@dataclass(frozen=True)
class NotificationsOutput:
    notifications: list[NotificationOutput]
    unread_count: int
    total_count: int
