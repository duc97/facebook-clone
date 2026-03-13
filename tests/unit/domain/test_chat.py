from __future__ import annotations

import pytest

from fb.domain.chat.entities import Message
from fb.domain.chat.exceptions import EmptyMessageError, MessageTooLongError
from fb.domain.shared.entity_id import EntityId


class TestMessageEntity:
    def test_create_with_valid_data(self) -> None:
        sender = EntityId.generate()
        receiver = EntityId.generate()
        message = Message.create(sender, receiver, "Hello!")

        assert message.sender_id == sender
        assert message.receiver_id == receiver
        assert message.content == "Hello!"
        assert message.is_seen is False
        assert message.id is not None

    def test_create_with_empty_content_raises(self) -> None:
        with pytest.raises(EmptyMessageError):
            Message.create(EntityId.generate(), EntityId.generate(), "")

    def test_create_with_whitespace_content_raises(self) -> None:
        with pytest.raises(EmptyMessageError):
            Message.create(EntityId.generate(), EntityId.generate(), "   ")

    def test_create_with_too_long_content_raises(self) -> None:
        with pytest.raises(MessageTooLongError):
            Message.create(EntityId.generate(), EntityId.generate(), "x" * 5001)

    def test_message_is_frozen(self) -> None:
        message = Message.create(EntityId.generate(), EntityId.generate(), "Hi")
        with pytest.raises(AttributeError):
            message.content = "modified"  # type: ignore[misc]

    def test_mark_seen_returns_new_instance(self) -> None:
        message = Message.create(EntityId.generate(), EntityId.generate(), "Hello")
        seen = message.mark_seen()

        assert seen.is_seen is True
        assert message.is_seen is False  # original unchanged
        assert seen.id == message.id

    def test_create_strips_whitespace(self) -> None:
        message = Message.create(EntityId.generate(), EntityId.generate(), "  hi  ")
        assert message.content == "hi"
