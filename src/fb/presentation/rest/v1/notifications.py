from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from fb.application.notification.get_notifications import GetNotificationsUseCase
from fb.application.notification.mark_read import MarkAllReadUseCase, MarkNotificationReadUseCase
from fb.container import Container
from fb.infrastructure.repositories.notification_repo import SqlAlchemyNotificationRepository
from fb.presentation.dependencies import get_container, get_current_user_id
from fb.presentation.rest.response import success_response
from fb.presentation.rest.v1.schemas import (
    NotificationResponse,
    NotificationsListResponse,
    UnreadCountResponse,
)

router = APIRouter(tags=["notifications"])


@router.get("/notifications")
async def get_notifications(
    limit: int = 20,
    offset: int = 0,
    unread_only: bool = False,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> Response:
    """Get notifications for the authenticated user."""
    async with container.session_factory() as session:
        notification_repo = SqlAlchemyNotificationRepository(session)
        use_case = GetNotificationsUseCase(notification_repo=notification_repo)
        result = await use_case.execute(
            user_id=current_user_id,
            limit=limit,
            offset=offset,
            unread_only=unread_only,
        )

    return success_response(
        NotificationsListResponse(
            notifications=[
                NotificationResponse(
                    id=n.id,
                    user_id=n.user_id,
                    actor_id=n.actor_id,
                    notification_type=n.notification_type,
                    entity_id=n.entity_id,
                    entity_type=n.entity_type,
                    message=n.message,
                    is_read=n.is_read,
                    created_at=n.created_at,
                )
                for n in result.notifications
            ],
            unread_count=result.unread_count,
            total_count=result.total_count,
        ).model_dump(),
    )


@router.get("/notifications/unread-count")
async def get_unread_count(
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> Response:
    """Get count of unread notifications."""
    # 1. Cache check — return immediately on hit
    cached = await container.cache.get_notif_unread(current_user_id)
    if cached is not None:
        return success_response(
            UnreadCountResponse(unread_count=cached).model_dump(),
        )

    # 2. DB fetch
    async with container.session_factory() as session:
        notification_repo = SqlAlchemyNotificationRepository(session)
        from fb.domain.shared.entity_id import EntityId

        uid = EntityId.from_str(current_user_id)
        count = await notification_repo.count_unread(uid)

    # 3. Cache and return
    await container.cache.set_notif_unread(current_user_id, count)
    return success_response(
        UnreadCountResponse(unread_count=count).model_dump(),
    )


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> Response:
    """Mark a single notification as read."""
    uow = container.create_uow()
    async with uow:
        notification_repo = SqlAlchemyNotificationRepository(uow.session)
        use_case = MarkNotificationReadUseCase(
            notification_repo=notification_repo, uow=uow
        )
        await use_case.execute(
            notification_id=notification_id,
            user_id=current_user_id,
        )

    await container.cache.invalidate_notif_unread(current_user_id)
    return success_response({"message": "Notification marked as read"})


@router.post("/notifications/read-all")
async def mark_all_read(
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> Response:
    """Mark all notifications as read."""
    uow = container.create_uow()
    async with uow:
        notification_repo = SqlAlchemyNotificationRepository(uow.session)
        use_case = MarkAllReadUseCase(
            notification_repo=notification_repo, uow=uow
        )
        await use_case.execute(user_id=current_user_id)

    await container.cache.invalidate_notif_unread(current_user_id)
    return success_response({"message": "All notifications marked as read"})
