from __future__ import annotations

from fb.application.chat.dtos import MessageOutput, SendMessageInput
from fb.application.shared.interfaces import UnitOfWork
from fb.domain.chat.entities import Message
from fb.domain.chat.exceptions import CannotMessageSelfError
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


class SendMessageUseCase:
    def __init__(self, message_repo: MessageRepository, uow: UnitOfWork) -> None:
        self._message_repo = message_repo
        self._uow = uow

    async def execute(self, input_data: SendMessageInput) -> MessageOutput:
        if input_data.sender_id == input_data.receiver_id:
            raise CannotMessageSelfError()

        sender = EntityId.from_str(input_data.sender_id)
        receiver = EntityId.from_str(input_data.receiver_id)
        message = Message.create(sender, receiver, input_data.content)
        saved = await self._message_repo.add(message)
        await self._uow.commit()
        return _to_output(saved)
