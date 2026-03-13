from __future__ import annotations

from datetime import datetime, timezone

import pytest

from fb.application.chat.dtos import GetMessagesInput, MessageOutput, SendMessageInput
from fb.application.chat.get_conversations import GetConversationsUseCase
from fb.application.chat.get_messages import GetMessagesUseCase
from fb.application.chat.send_message import SendMessageUseCase
from fb.domain.chat.entities import Conversation, Message
from fb.domain.chat.exceptions import CannotMessageSelfError
from fb.domain.shared.entity_id import EntityId
from fb.domain.shared.pagination import CursorPage, PageInfo


class FakeMessageRepo:
    def __init__(self) -> None:
        self._messages: list[Message] = []

    async def add(self, message: Message) -> Message:
        self._messages.append(message)
        return message

    async def find_by_id(self, message_id: EntityId) -> Message | None:
        for m in self._messages:
            if m.id == message_id:
                return m
        return None

    async def mark_seen(self, message_id: EntityId) -> None:
        for i, m in enumerate(self._messages):
            if m.id == message_id:
                self._messages[i] = m.mark_seen()
                return

    async def mark_conversation_seen(
        self, user_id: EntityId, other_user_id: EntityId
    ) -> None:
        self._messages = [
            m.mark_seen()
            if m.sender_id == other_user_id and m.receiver_id == user_id and not m.is_seen
            else m
            for m in self._messages
        ]

    async def get_conversation_messages(
        self,
        user_id: EntityId,
        other_user_id: EntityId,
        first: int = 20,
        after_cursor: str | None = None,
    ) -> CursorPage[Message]:
        filtered = [
            m
            for m in self._messages
            if (m.sender_id == user_id and m.receiver_id == other_user_id)
            or (m.sender_id == other_user_id and m.receiver_id == user_id)
        ]
        items = filtered[:first]
        return CursorPage(
            items=tuple(items),
            page_info=PageInfo(
                has_next_page=len(filtered) > first,
                has_previous_page=False,
            ),
            total_count=len(filtered),
        )

    async def get_conversations(
        self, user_id: EntityId, limit: int = 20, offset: int = 0
    ) -> list[Conversation]:
        partners: dict[str, list[Message]] = {}
        for m in self._messages:
            if m.sender_id == user_id:
                key = str(m.receiver_id)
            elif m.receiver_id == user_id:
                key = str(m.sender_id)
            else:
                continue
            partners.setdefault(key, []).append(m)

        result: list[Conversation] = []
        for partner_id_str, msgs in list(partners.items())[offset : offset + limit]:
            last = msgs[-1]
            unread = sum(
                1
                for m in msgs
                if m.sender_id == EntityId.from_str(partner_id_str)
                and m.receiver_id == user_id
                and not m.is_seen
            )
            result.append(
                Conversation(
                    user_id=user_id,
                    other_user_id=EntityId.from_str(partner_id_str),
                    last_message=last,
                    unread_count=unread,
                )
            )
        return result

    async def get_unread_count(self, user_id: EntityId) -> int:
        return sum(
            1
            for m in self._messages
            if m.receiver_id == user_id and not m.is_seen
        )


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.committed = False

    async def __aenter__(self) -> FakeUnitOfWork:
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass


class TestSendMessageUseCase:
    async def test_send_message_succeeds(self) -> None:
        repo = FakeMessageRepo()
        uow = FakeUnitOfWork()
        use_case = SendMessageUseCase(repo, uow)
        sender_id = str(EntityId.generate())
        receiver_id = str(EntityId.generate())

        result = await use_case.execute(
            SendMessageInput(
                sender_id=sender_id,
                receiver_id=receiver_id,
                content="Hello!",
            )
        )

        assert isinstance(result, MessageOutput)
        assert result.sender_id == sender_id
        assert result.receiver_id == receiver_id
        assert result.content == "Hello!"
        assert result.is_seen is False
        assert uow.committed is True

    async def test_send_message_to_self_raises(self) -> None:
        repo = FakeMessageRepo()
        uow = FakeUnitOfWork()
        use_case = SendMessageUseCase(repo, uow)
        same_id = str(EntityId.generate())

        with pytest.raises(CannotMessageSelfError):
            await use_case.execute(
                SendMessageInput(
                    sender_id=same_id,
                    receiver_id=same_id,
                    content="Hello myself",
                )
            )


class TestGetMessagesUseCase:
    async def test_returns_paginated_messages(self) -> None:
        repo = FakeMessageRepo()
        user_id = EntityId.generate()
        other_id = EntityId.generate()

        msg = Message.create(user_id, other_id, "Hey there")
        await repo.add(msg)

        use_case = GetMessagesUseCase(repo)
        result = await use_case.execute(
            GetMessagesInput(
                user_id=str(user_id),
                other_user_id=str(other_id),
            )
        )

        assert len(result.messages) == 1
        assert result.messages[0].content == "Hey there"
        assert result.total_count == 1
        assert result.page_info["has_next_page"] is False


class TestGetConversationsUseCase:
    async def test_returns_conversation_list(self) -> None:
        repo = FakeMessageRepo()
        user_id = EntityId.generate()
        other_id = EntityId.generate()

        msg = Message.create(other_id, user_id, "Hi!")
        await repo.add(msg)

        use_case = GetConversationsUseCase(repo)
        result = await use_case.execute(user_id=str(user_id))

        assert len(result) == 1
        assert result[0].other_user_id == str(other_id)
        assert result[0].unread_count == 1
        assert result[0].last_message is not None
        assert result[0].last_message.content == "Hi!"
