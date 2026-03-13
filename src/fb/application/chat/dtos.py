from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SendMessageInput:
    sender_id: str
    receiver_id: str
    content: str


@dataclass(frozen=True)
class MessageOutput:
    id: str
    sender_id: str
    receiver_id: str
    content: str
    is_seen: bool
    created_at: str | None


@dataclass(frozen=True)
class ConversationOutput:
    other_user_id: str
    last_message: MessageOutput | None
    unread_count: int


@dataclass(frozen=True)
class GetMessagesInput:
    user_id: str
    other_user_id: str
    first: int = 20
    after: str | None = None


@dataclass(frozen=True)
class MessagesOutput:
    messages: list[MessageOutput]
    total_count: int
    page_info: dict[str, Any]
