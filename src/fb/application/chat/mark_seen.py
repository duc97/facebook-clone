from __future__ import annotations

from fb.application.shared.interfaces import UnitOfWork
from fb.domain.chat.repository import MessageRepository
from fb.domain.shared.entity_id import EntityId


class MarkConversationSeenUseCase:
    def __init__(self, message_repo: MessageRepository, uow: UnitOfWork) -> None:
        self._message_repo = message_repo
        self._uow = uow

    async def execute(self, user_id: str, other_user_id: str) -> None:
        user = EntityId.from_str(user_id)
        other = EntityId.from_str(other_user_id)
        await self._message_repo.mark_conversation_seen(user, other)
        await self._uow.commit()
