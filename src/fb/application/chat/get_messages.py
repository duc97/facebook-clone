from __future__ import annotations

from fb.application.chat.dtos import GetMessagesInput, MessageOutput, MessagesOutput
from fb.domain.chat.entities import Message
from fb.domain.chat.repository import MessageRepository
from fb.domain.shared.entity_id import EntityId


def _to_output(message: Message) -> MessageOutput:
    return MessageOutput(
        id=str(message.id),
        sender_id=str(message.sender_id),
        receiver_id=str(message.receiver_id),
        content=message.content,
        is_seen=message.is_seen,
        created_at=message.created_at.isoformat() if message.created_at else None,
    )


class GetMessagesUseCase:
    def __init__(self, message_repo: MessageRepository) -> None:
        self._message_repo = message_repo

    async def execute(self, input_data: GetMessagesInput) -> MessagesOutput:
        user = EntityId.from_str(input_data.user_id)
        other = EntityId.from_str(input_data.other_user_id)
        page = await self._message_repo.get_conversation_messages(
            user,
            other,
            first=input_data.first,
            after_cursor=input_data.after,
        )
        return MessagesOutput(
            messages=[_to_output(m) for m in page.items],
            total_count=page.total_count,
            page_info={
                "has_next_page": page.page_info.has_next_page,
                "has_previous_page": page.page_info.has_previous_page,
                "start_cursor": page.page_info.start_cursor,
                "end_cursor": page.page_info.end_cursor,
            },
        )
