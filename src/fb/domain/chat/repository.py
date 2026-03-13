from __future__ import annotations

from typing import Protocol, runtime_checkable

from fb.domain.chat.entities import Conversation, Message
from fb.domain.shared.entity_id import EntityId
from fb.domain.shared.pagination import CursorPage


@runtime_checkable
class MessageRepository(Protocol):
    async def add(self, message: Message) -> Message: ...
    async def find_by_id(self, message_id: EntityId) -> Message | None: ...
    async def mark_seen(self, message_id: EntityId) -> None: ...
    async def mark_conversation_seen(
        self, user_id: EntityId, other_user_id: EntityId
    ) -> None: ...
    async def get_conversation_messages(
        self,
        user_id: EntityId,
        other_user_id: EntityId,
        first: int = 20,
        after_cursor: str | None = None,
    ) -> CursorPage[Message]: ...
    async def get_conversations(
        self, user_id: EntityId, limit: int = 20, offset: int = 0
    ) -> list[Conversation]: ...
    async def get_unread_count(self, user_id: EntityId) -> int: ...
