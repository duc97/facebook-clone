from __future__ import annotations

import pytest

from fb.domain.notification.entities import Notification, NotificationType
from fb.domain.notification.exceptions import NotificationNotFoundError
from fb.domain.shared.entity_id import EntityId


class TestNotificationEntity:
    def test_create_notification(self) -> None:
        user_id = EntityId.generate()
        actor_id = EntityId.generate()
        notification = Notification.create(
            user_id=user_id,
            actor_id=actor_id,
            notification_type=NotificationType.LIKE,
            entity_id="post-123",
            entity_type="post",
            message="John liked your post",
        )

        assert notification.user_id == user_id
        assert notification.actor_id == actor_id
        assert notification.notification_type == NotificationType.LIKE
        assert notification.entity_id == "post-123"
        assert notification.entity_type == "post"
        assert notification.message == "John liked your post"
        assert notification.is_read is False
        assert notification.id is not None

    def test_notification_is_frozen(self) -> None:
        notification = Notification.create(
            user_id=EntityId.generate(),
            actor_id=EntityId.generate(),
            notification_type=NotificationType.COMMENT,
            entity_id="post-456",
            entity_type="post",
            message="Someone commented",
        )
        with pytest.raises(AttributeError):
            notification.is_read = True  # type: ignore[misc]

    def test_mark_read_returns_new_instance(self) -> None:
        notification = Notification.create(
            user_id=EntityId.generate(),
            actor_id=EntityId.generate(),
            notification_type=NotificationType.LIKE,
            entity_id="post-123",
            entity_type="post",
            message="John liked your post",
        )
        read_notification = notification.mark_read()

        assert read_notification.is_read is True
        assert notification.is_read is False  # original unchanged
        assert read_notification.id == notification.id

    def test_all_notification_types_exist(self) -> None:
        expected = {
            "like", "comment", "friend_request", "friend_accept",
            "mention", "share", "reaction", "message",
        }
        actual = {t.value for t in NotificationType}
        assert actual == expected

    def test_notification_not_found_error(self) -> None:
        error = NotificationNotFoundError()
        assert str(error) == "Notification not found"
        assert isinstance(error, Exception)
