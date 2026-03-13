from __future__ import annotations

from fb.application.chat.dtos import ConversationOutput, MessageOutput
from fb.domain.chat.entities import Conversation
from fb.domain.chat.repository import MessageRepository
from fb.domain.shared.entity_id import EntityId


def _message_to_output(message: object) -> MessageOutput | None:
    if message is None:
        return None
    from fb.domain.chat.entities import Message

    assert isinstance(message, Message)
    return MessageOutput(
        id=str(message.id),
        sender_id=str(message.sender_id),
        receiver_id=str(message.receiver_id),
        content=message.content,
        is_seen=message.is_seen,
        created_at=message.created_at.isoformat() if message.created_at else None,
    )


def _to_output(conversation: Conversation) -> ConversationOutput:
    return ConversationOutput(
        other_user_id=str(conversation.other_user_id),
        last_message=_message_to_output(conversation.last_message),
        unread_count=conversation.unread_count,
    )


class GetConversationsUseCase:
    def __init__(self, message_repo: MessageRepository) -> None:
        self._message_repo = message_repo

    async def execute(
        self, user_id: str, limit: int = 20, offset: int = 0
    ) -> list[ConversationOutput]:
        user = EntityId.from_str(user_id)
        conversations = await self._message_repo.get_conversations(
            user, limit=limit, offset=offset
        )
        return [_to_output(c) for c in conversations]
