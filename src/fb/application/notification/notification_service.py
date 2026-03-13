from __future__ import annotations

from typing import Any

from fb.application.notification.dtos import NotificationOutput
from fb.application.shared.interfaces import UnitOfWork
from fb.domain.notification.entities import Notification, NotificationType
from fb.domain.notification.repository import NotificationRepository
from fb.domain.shared.entity_id import EntityId


def _to_output(notification: Notification) -> NotificationOutput:
    return NotificationOutput(
        id=str(notification.id),
        user_id=str(notification.user_id),
        actor_id=str(notification.actor_id),
        notification_type=notification.notification_type.value,
        entity_id=notification.entity_id,
        entity_type=notification.entity_type,
        message=notification.message,
        is_read=notification.is_read,
        created_at=notification.created_at.isoformat() if notification.created_at else None,
    )


class NotificationService:
    """Facade for creating notifications and pushing them via pubsub."""

    def __init__(
        self,
        notification_repo: NotificationRepository,
        uow: UnitOfWork,
        pubsub: Any | None = None,
    ) -> None:
        self._repo = notification_repo
        self._uow = uow
        self._pubsub = pubsub

    async def notify_like(
        self,
        post_author_id: str,
        liker_id: str,
        post_id: str,
        liker_name: str = "Someone",
    ) -> NotificationOutput | None:
        if post_author_id == liker_id:
            return None
        return await self._create(
            user_id=post_author_id,
            actor_id=liker_id,
            notification_type="like",
            entity_id=post_id,
            entity_type="post",
            message=f"{liker_name} liked your post",
        )

    async def notify_comment(
        self,
        post_author_id: str,
        commenter_id: str,
        post_id: str,
        commenter_name: str = "Someone",
    ) -> NotificationOutput | None:
        if post_author_id == commenter_id:
            return None
        return await self._create(
            user_id=post_author_id,
            actor_id=commenter_id,
            notification_type="comment",
            entity_id=post_id,
            entity_type="post",
            message=f"{commenter_name} commented on your post",
        )

    async def notify_friend_request(
        self,
        receiver_id: str,
        sender_id: str,
        request_id: str,
        sender_name: str = "Someone",
    ) -> NotificationOutput | None:
        return await self._create(
            user_id=receiver_id,
            actor_id=sender_id,
            notification_type="friend_request",
            entity_id=request_id,
            entity_type="friend_request",
            message=f"{sender_name} sent you a friend request",
        )

    async def notify_friend_accept(
        self,
        sender_id: str,
        acceptor_id: str,
        request_id: str,
        acceptor_name: str = "Someone",
    ) -> NotificationOutput | None:
        return await self._create(
            user_id=sender_id,
            actor_id=acceptor_id,
            notification_type="friend_accept",
            entity_id=request_id,
            entity_type="friend_request",
            message=f"{acceptor_name} accepted your friend request",
        )

    async def notify_share(
        self,
        post_author_id: str,
        sharer_id: str,
        post_id: str,
        sharer_name: str = "Someone",
    ) -> NotificationOutput | None:
        if post_author_id == sharer_id:
            return None
        return await self._create(
            user_id=post_author_id,
            actor_id=sharer_id,
            notification_type="share",
            entity_id=post_id,
            entity_type="post",
            message=f"{sharer_name} shared your post",
        )

    async def notify_reaction(
        self,
        post_author_id: str,
        reactor_id: str,
        post_id: str,
        reaction_type: str,
        reactor_name: str = "Someone",
    ) -> NotificationOutput | None:
        if post_author_id == reactor_id:
            return None
        return await self._create(
            user_id=post_author_id,
            actor_id=reactor_id,
            notification_type="reaction",
            entity_id=post_id,
            entity_type="post",
            message=f"{reactor_name} reacted {reaction_type} to your post",
        )

    async def _create(self, **kwargs: str) -> NotificationOutput:
        notification = Notification.create(
            user_id=EntityId.from_str(kwargs["user_id"]),
            actor_id=EntityId.from_str(kwargs["actor_id"]),
            notification_type=NotificationType(kwargs["notification_type"]),
            entity_id=kwargs["entity_id"],
            entity_type=kwargs["entity_type"],
            message=kwargs["message"],
        )
        saved = await self._repo.add(notification)
        await self._uow.commit()
        output = _to_output(saved)

        if self._pubsub is not None:
            await self._pubsub.publish(
                output.user_id,
                {
                    "type": "notification.new",
                    "data": {
                        "id": output.id,
                        "notification_type": output.notification_type,
                        "message": output.message,
                        "entity_id": output.entity_id,
                        "entity_type": output.entity_type,
                        "actor_id": output.actor_id,
                        "is_read": output.is_read,
                        "created_at": output.created_at,
                    },
                },
            )

        return output
