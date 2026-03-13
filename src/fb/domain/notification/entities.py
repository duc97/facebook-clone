from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum

from fb.domain.shared.entity_id import EntityId


class NotificationType(str, Enum):
    LIKE = "like"
    COMMENT = "comment"
    FRIEND_REQUEST = "friend_request"
    FRIEND_ACCEPT = "friend_accept"
    MENTION = "mention"
    SHARE = "share"
    REACTION = "reaction"
    MESSAGE = "message"


@dataclass(frozen=True, slots=True)
class Notification:
    """Notification entity representing a user notification."""

    id: EntityId
    user_id: EntityId  # who receives the notification
    actor_id: EntityId  # who triggered it
    notification_type: NotificationType
    entity_id: str  # the related entity (post_id, comment_id, message_id, etc.)
    entity_type: str  # "post", "comment", "friend_request", "message"
    message: str  # human-readable: "John liked your post"
    is_read: bool = False
    created_at: datetime | None = None

    @classmethod
    def create(
        cls,
        user_id: EntityId,
        actor_id: EntityId,
        notification_type: NotificationType,
        entity_id: str,
        entity_type: str,
        message: str,
    ) -> Notification:
        return cls(
            id=EntityId.generate(),
            user_id=user_id,
            actor_id=actor_id,
            notification_type=notification_type,
            entity_id=entity_id,
            entity_type=entity_type,
            message=message,
        )

    def mark_read(self) -> Notification:
        return replace(self, is_read=True)
