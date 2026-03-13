from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from fb.domain.chat.exceptions import EmptyMessageError, MessageTooLongError
from fb.domain.shared.entity_id import EntityId


@dataclass(frozen=True, slots=True)
class Message:
    """Represents a chat message between two users."""

    id: EntityId
    sender_id: EntityId
    receiver_id: EntityId
    content: str
    is_seen: bool = False
    created_at: datetime | None = None

    @classmethod
    def create(
        cls,
        sender_id: EntityId,
        receiver_id: EntityId,
        content: str,
    ) -> Message:
        if not content or not content.strip():
            raise EmptyMessageError()
        if len(content) > 5000:
            raise MessageTooLongError()
        return cls(
            id=EntityId.generate(),
            sender_id=sender_id,
            receiver_id=receiver_id,
            content=content.strip(),
        )

    def mark_seen(self) -> Message:
        return replace(self, is_seen=True)


@dataclass(frozen=True, slots=True)
class Conversation:
    """Represents a conversation between two users."""

    user_id: EntityId
    other_user_id: EntityId
    last_message: Message | None = None
    unread_count: int = 0
