from __future__ import annotations

import pytest

from fb.application.notification.create_notification import CreateNotificationUseCase
from fb.application.notification.dtos import CreateNotificationInput, NotificationOutput
from fb.application.notification.get_notifications import GetNotificationsUseCase
from fb.application.notification.mark_read import MarkAllReadUseCase, MarkNotificationReadUseCase
from fb.application.notification.notification_service import NotificationService
from fb.domain.notification.entities import Notification, NotificationType
from fb.domain.notification.exceptions import NotificationNotFoundError
from fb.domain.shared.entity_id import EntityId


class FakeNotificationRepo:
    def __init__(self) -> None:
        self._notifications: list[Notification] = []

    async def add(self, notification: Notification) -> Notification:
        self._notifications.append(notification)
        return notification

    async def find_by_id(self, notification_id: EntityId) -> Notification | None:
        for n in self._notifications:
            if n.id == notification_id:
                return n
        return None

    async def get_by_user(
        self,
        user_id: EntityId,
        limit: int = 20,
        offset: int = 0,
        unread_only: bool = False,
    ) -> list[Notification]:
        filtered = [n for n in self._notifications if n.user_id == user_id]
        if unread_only:
            filtered = [n for n in filtered if not n.is_read]
        return filtered[offset : offset + limit]

    async def count_unread(self, user_id: EntityId) -> int:
        return len([
            n for n in self._notifications
            if n.user_id == user_id and not n.is_read
        ])

    async def mark_read(self, notification_id: EntityId) -> None:
        for i, n in enumerate(self._notifications):
            if n.id == notification_id:
                self._notifications[i] = n.mark_read()
                return

    async def mark_all_read(self, user_id: EntityId) -> None:
        self._notifications = [
            n.mark_read() if n.user_id == user_id and not n.is_read else n
            for n in self._notifications
        ]


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


class TestCreateNotificationUseCase:
    async def test_create_notification_succeeds(self) -> None:
        repo = FakeNotificationRepo()
        uow = FakeUnitOfWork()
        use_case = CreateNotificationUseCase(repo, uow)
        user_id = str(EntityId.generate())
        actor_id = str(EntityId.generate())

        result = await use_case.execute(
            CreateNotificationInput(
                user_id=user_id,
                actor_id=actor_id,
                notification_type="like",
                entity_id="post-123",
                entity_type="post",
                message="John liked your post",
            )
        )

        assert isinstance(result, NotificationOutput)
        assert result.user_id == user_id
        assert result.actor_id == actor_id
        assert result.notification_type == "like"
        assert result.message == "John liked your post"
        assert uow.committed is True

    async def test_self_notification_skipped(self) -> None:
        repo = FakeNotificationRepo()
        uow = FakeUnitOfWork()
        use_case = CreateNotificationUseCase(repo, uow)
        same_id = str(EntityId.generate())

        result = await use_case.execute(
            CreateNotificationInput(
                user_id=same_id,
                actor_id=same_id,
                notification_type="like",
                entity_id="post-123",
                entity_type="post",
                message="You liked your own post",
            )
        )

        assert result.id == ""  # dummy output
        assert len(repo._notifications) == 0  # nothing saved


class TestGetNotificationsUseCase:
    async def test_get_notifications_returns_list(self) -> None:
        repo = FakeNotificationRepo()
        user_id = EntityId.generate()
        actor_id = EntityId.generate()

        # Add a notification
        notification = Notification.create(
            user_id=user_id,
            actor_id=actor_id,
            notification_type=NotificationType.LIKE,
            entity_id="post-123",
            entity_type="post",
            message="John liked your post",
        )
        await repo.add(notification)

        use_case = GetNotificationsUseCase(repo)
        result = await use_case.execute(user_id=str(user_id))

        assert len(result.notifications) == 1
        assert result.unread_count == 1
        assert result.notifications[0].notification_type == "like"


class TestMarkReadUseCase:
    async def test_mark_read_succeeds(self) -> None:
        repo = FakeNotificationRepo()
        uow = FakeUnitOfWork()
        user_id = EntityId.generate()
        notification = Notification.create(
            user_id=user_id,
            actor_id=EntityId.generate(),
            notification_type=NotificationType.LIKE,
            entity_id="post-123",
            entity_type="post",
            message="Liked",
        )
        await repo.add(notification)

        use_case = MarkNotificationReadUseCase(repo, uow)
        await use_case.execute(
            notification_id=str(notification.id),
            user_id=str(user_id),
        )

        updated = await repo.find_by_id(notification.id)
        assert updated is not None
        assert updated.is_read is True
        assert uow.committed is True

    async def test_mark_read_wrong_user_raises_not_found(self) -> None:
        repo = FakeNotificationRepo()
        uow = FakeUnitOfWork()
        user_id = EntityId.generate()
        other_user_id = EntityId.generate()
        notification = Notification.create(
            user_id=user_id,
            actor_id=EntityId.generate(),
            notification_type=NotificationType.LIKE,
            entity_id="post-123",
            entity_type="post",
            message="Liked",
        )
        await repo.add(notification)

        use_case = MarkNotificationReadUseCase(repo, uow)
        with pytest.raises(NotificationNotFoundError):
            await use_case.execute(
                notification_id=str(notification.id),
                user_id=str(other_user_id),
            )

    async def test_mark_all_read_succeeds(self) -> None:
        repo = FakeNotificationRepo()
        uow = FakeUnitOfWork()
        user_id = EntityId.generate()

        for i in range(3):
            n = Notification.create(
                user_id=user_id,
                actor_id=EntityId.generate(),
                notification_type=NotificationType.COMMENT,
                entity_id=f"post-{i}",
                entity_type="post",
                message=f"Comment {i}",
            )
            await repo.add(n)

        use_case = MarkAllReadUseCase(repo, uow)
        await use_case.execute(user_id=str(user_id))

        unread = await repo.count_unread(user_id)
        assert unread == 0
        assert uow.committed is True


class TestNotificationService:
    async def test_notify_like_creates_notification(self) -> None:
        repo = FakeNotificationRepo()
        uow = FakeUnitOfWork()
        service = NotificationService(repo, uow)

        author_id = str(EntityId.generate())
        liker_id = str(EntityId.generate())

        result = await service.notify_like(
            post_author_id=author_id,
            liker_id=liker_id,
            post_id="post-123",
            liker_name="John",
        )

        assert result is not None
        assert result.notification_type == "like"
        assert result.message == "John liked your post"
        assert result.user_id == author_id

    async def test_notify_comment_creates_notification(self) -> None:
        repo = FakeNotificationRepo()
        uow = FakeUnitOfWork()
        service = NotificationService(repo, uow)

        author_id = str(EntityId.generate())
        commenter_id = str(EntityId.generate())

        result = await service.notify_comment(
            post_author_id=author_id,
            commenter_id=commenter_id,
            post_id="post-456",
            commenter_name="Jane",
        )

        assert result is not None
        assert result.notification_type == "comment"
        assert result.message == "Jane commented on your post"

    async def test_service_skips_self_notifications(self) -> None:
        repo = FakeNotificationRepo()
        uow = FakeUnitOfWork()
        service = NotificationService(repo, uow)

        same_id = str(EntityId.generate())

        result = await service.notify_like(
            post_author_id=same_id,
            liker_id=same_id,
            post_id="post-123",
        )

        assert result is None
        assert len(repo._notifications) == 0
