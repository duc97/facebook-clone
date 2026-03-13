from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, Response

from fb.application.friend.accept_request import AcceptRequestUseCase
from fb.application.friend.dtos import (
    AcceptRequestInput as AcceptDTO,
    MutualFriendsInput as MutualDTO,
    RejectRequestInput as RejectDTO,
    SendRequestInput as SendDTO,
    UnfriendInput as UnfriendDTO,
)
from fb.application.friend.mutual_friends import MutualFriendsUseCase
from fb.application.friend.reject_request import RejectRequestUseCase
from fb.application.friend.send_request import SendRequestUseCase
from fb.application.friend.unfriend import UnfriendUseCase
from fb.application.notification.notification_service import NotificationService
from fb.container import Container
from fb.domain.shared.entity_id import EntityId
from fb.infrastructure.repositories.friend_repo import SqlAlchemyFriendRepository
from fb.infrastructure.repositories.notification_repo import SqlAlchemyNotificationRepository
from fb.presentation.dependencies import get_container, get_current_user_id
from fb.presentation.rest.response import success_response
from fb.presentation.rest.v1.schemas import (
    FriendListResponse,
    FriendRequestResponse,
    MessageResponse,
    SendFriendRequestBody,
)

router = APIRouter(tags=["friends"])

_logger = logging.getLogger(__name__)


# ── Background notification helpers ─────────────────────────────────────


async def _notify_friend_request(
    container: Container, request_id: str, sender_id: str, receiver_id: str
) -> None:
    """Fire-and-forget: notify receiver about an incoming friend request."""
    try:
        uow = container.create_uow()
        async with uow:
            notif_repo = SqlAlchemyNotificationRepository(uow.session)
            svc = NotificationService(
                notification_repo=notif_repo,
                uow=uow,
                pubsub=container.pubsub,
            )
            await svc.notify_friend_request(
                receiver_id=receiver_id,
                sender_id=sender_id,
                request_id=request_id,
            )
    except Exception:
        _logger.exception(
            "_notify_friend_request failed for request=%s sender=%s",
            request_id,
            sender_id,
        )


async def _notify_friend_accept(
    container: Container, request_id: str, sender_id: str, acceptor_id: str
) -> None:
    """Fire-and-forget: notify original sender that their request was accepted."""
    try:
        uow = container.create_uow()
        async with uow:
            notif_repo = SqlAlchemyNotificationRepository(uow.session)
            svc = NotificationService(
                notification_repo=notif_repo,
                uow=uow,
                pubsub=container.pubsub,
            )
            await svc.notify_friend_accept(
                sender_id=sender_id,
                acceptor_id=acceptor_id,
                request_id=request_id,
            )
    except Exception:
        _logger.exception(
            "_notify_friend_accept failed for request=%s acceptor=%s",
            request_id,
            acceptor_id,
        )


@router.post("/friends/requests", status_code=201)
async def send_friend_request(
    body: SendFriendRequestBody,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
):
    """Send a friend request to another user."""
    uow = container.create_uow()
    async with uow:
        friend_repo = SqlAlchemyFriendRepository(uow.session)
        use_case = SendRequestUseCase(friend_repo=friend_repo, uow=uow)
        result = await use_case.execute(
            SendDTO(
                sender_id=current_user_id,
                receiver_id=body.receiver_id,
            )
        )

    asyncio.create_task(
        _notify_friend_request(container, result.id, current_user_id, body.receiver_id)
    )

    return success_response(
        FriendRequestResponse(
            id=result.id,
            sender_id=result.sender_id,
            receiver_id=result.receiver_id,
            status=result.status,
        ).model_dump(),
        status_code=201,
    )


@router.post("/friends/requests/{request_id}/accept")
async def accept_friend_request(
    request_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
):
    """Accept a pending friend request."""
    uow = container.create_uow()
    async with uow:
        friend_repo = SqlAlchemyFriendRepository(uow.session)
        use_case = AcceptRequestUseCase(friend_repo=friend_repo, uow=uow)
        result = await use_case.execute(
            AcceptDTO(
                request_id=request_id,
                user_id=current_user_id,
            )
        )

    asyncio.create_task(
        _notify_friend_accept(container, request_id, result.sender_id, current_user_id)
    )

    return success_response(
        FriendRequestResponse(
            id=result.id,
            sender_id=result.sender_id,
            receiver_id=result.receiver_id,
            status=result.status,
        ).model_dump(),
    )


@router.post("/friends/requests/{request_id}/reject")
async def reject_friend_request(
    request_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
):
    """Reject a pending friend request."""
    uow = container.create_uow()
    async with uow:
        friend_repo = SqlAlchemyFriendRepository(uow.session)
        use_case = RejectRequestUseCase(friend_repo=friend_repo, uow=uow)
        await use_case.execute(
            RejectDTO(
                request_id=request_id,
                user_id=current_user_id,
            )
        )

    return success_response(
        MessageResponse(message="Friend request rejected").model_dump(),
    )


@router.delete("/friends/{friend_id}", status_code=204)
async def unfriend(
    friend_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> Response:
    """Remove a friendship."""
    uow = container.create_uow()
    async with uow:
        friend_repo = SqlAlchemyFriendRepository(uow.session)
        use_case = UnfriendUseCase(friend_repo=friend_repo, uow=uow)
        await use_case.execute(
            UnfriendDTO(
                user_id=current_user_id,
                friend_id=friend_id,
            )
        )

    return Response(status_code=204)


@router.get("/friends/requests/pending")
async def get_pending_requests(
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
):
    """List all pending friend requests for the authenticated user."""
    async with container.session_factory() as session:
        friend_repo = SqlAlchemyFriendRepository(session)
        uid = EntityId.from_str(current_user_id)
        requests = await friend_repo.get_pending_requests(uid)

    items = [
        FriendRequestResponse(
            id=str(r.id),
            sender_id=str(r.sender_id),
            receiver_id=str(r.receiver_id),
            status=r.status.value,
        ).model_dump()
        for r in requests
    ]

    return success_response(items)


@router.get("/friends/mutual/{user_id}")
async def get_mutual_friends(
    user_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
):
    """Get mutual friends between the authenticated user and another user."""
    async with container.session_factory() as session:
        friend_repo = SqlAlchemyFriendRepository(session)
        use_case = MutualFriendsUseCase(friend_repo=friend_repo)
        result = await use_case.execute(
            MutualDTO(
                user_id=current_user_id,
                other_id=user_id,
            )
        )

    return success_response(
        FriendListResponse(
            friend_ids=result.friend_ids,
            total_count=result.total_count,
        ).model_dump(),
    )
