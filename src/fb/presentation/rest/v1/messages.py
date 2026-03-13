from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Response

from fb.application.chat.get_conversations import GetConversationsUseCase
from fb.application.chat.get_messages import GetMessagesUseCase
from fb.application.chat.mark_seen import MarkConversationSeenUseCase
from fb.application.chat.send_message import SendMessageUseCase
from fb.application.chat.dtos import GetMessagesInput, SendMessageInput
from fb.container import Container
from fb.infrastructure.repositories.message_repo import SqlAlchemyMessageRepository
from fb.presentation.dependencies import get_container, get_current_user_id
from fb.presentation.rest.response import paginated_response, success_response
from fb.presentation.rest.v1.schemas import (
    ChatConversationResponse,
    ChatMessageResponse,
    SendMessageRequest,
)

router = APIRouter(tags=["messages"])


@router.get("/messages/conversations")
async def get_conversations(
    limit: int = 20,
    offset: int = 0,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> Response:
    """List conversations for the authenticated user."""
    async with container.session_factory() as session:
        message_repo = SqlAlchemyMessageRepository(session)
        use_case = GetConversationsUseCase(message_repo=message_repo)
        result = await use_case.execute(
            user_id=current_user_id,
            limit=limit,
            offset=offset,
        )

    return success_response(
        [
            ChatConversationResponse(
                other_user_id=c.other_user_id,
                last_message=ChatMessageResponse(
                    id=c.last_message.id,
                    sender_id=c.last_message.sender_id,
                    receiver_id=c.last_message.receiver_id,
                    content=c.last_message.content,
                    is_seen=c.last_message.is_seen,
                    created_at=c.last_message.created_at,
                )
                if c.last_message
                else None,
                unread_count=c.unread_count,
            ).model_dump()
            for c in result
        ],
    )


@router.get("/messages/unread-count")
async def get_unread_count(
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> Response:
    """Return the total number of unread messages for the authenticated user."""
    from fb.domain.shared.entity_id import EntityId
    async with container.session_factory() as session:
        message_repo = SqlAlchemyMessageRepository(session)
        uid = EntityId.from_str(current_user_id)
        count = await message_repo.get_unread_count(uid)
    return success_response({"unread_count": count})


@router.get("/messages/{user_id}")
async def get_messages(
    user_id: str,
    first: int = 20,
    after: str | None = None,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> Response:
    """Get message history with a specific user, cursor-paginated."""
    async with container.session_factory() as session:
        message_repo = SqlAlchemyMessageRepository(session)
        use_case = GetMessagesUseCase(message_repo=message_repo)
        result = await use_case.execute(
            GetMessagesInput(
                user_id=current_user_id,
                other_user_id=user_id,
                first=first,
                after=after,
            )
        )

    messages = [
        ChatMessageResponse(
            id=m.id,
            sender_id=m.sender_id,
            receiver_id=m.receiver_id,
            content=m.content,
            is_seen=m.is_seen,
            created_at=m.created_at,
        ).model_dump()
        for m in result.messages
    ]

    return paginated_response(
        data=messages,
        total=result.total_count,
        limit=first,
        cursor=result.page_info.get("end_cursor"),
        has_next=result.page_info.get("has_next_page", False),
    )


@router.post("/messages/{user_id}", status_code=201)
async def send_message(
    user_id: str,
    body: SendMessageRequest,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> Response:
    """Send a message to a user."""
    uow = container.create_uow()
    async with uow:
        message_repo = SqlAlchemyMessageRepository(uow.session)
        use_case = SendMessageUseCase(message_repo=message_repo, uow=uow)
        result = await use_case.execute(
            SendMessageInput(
                sender_id=current_user_id,
                receiver_id=user_id,
                content=body.content,
            )
        )

    asyncio.create_task(_push_message(container, result))

    return success_response(
        ChatMessageResponse(
            id=result.id,
            sender_id=result.sender_id,
            receiver_id=result.receiver_id,
            content=result.content,
            is_seen=result.is_seen,
            created_at=result.created_at,
        ).model_dump(),
        status_code=201,
    )


async def _push_message(container: Container, msg_output: object) -> None:
    """Fire-and-forget: publish a realtime chat.message event to the receiver."""
    try:
        await container.pubsub.publish(
            msg_output.receiver_id,  # type: ignore[attr-defined]
            {
                "type": "chat.message",
                "data": {
                    "id": msg_output.id,  # type: ignore[attr-defined]
                    "sender_id": msg_output.sender_id,  # type: ignore[attr-defined]
                    "receiver_id": msg_output.receiver_id,  # type: ignore[attr-defined]
                    "content": msg_output.content,  # type: ignore[attr-defined]
                    "is_seen": msg_output.is_seen,  # type: ignore[attr-defined]
                    "created_at": msg_output.created_at,  # type: ignore[attr-defined]
                },
            },
        )
    except Exception:
        pass


@router.post("/messages/{user_id}/seen")
async def mark_conversation_seen(
    user_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> Response:
    """Mark all messages from user_id as seen."""
    uow = container.create_uow()
    async with uow:
        message_repo = SqlAlchemyMessageRepository(uow.session)
        use_case = MarkConversationSeenUseCase(message_repo=message_repo, uow=uow)
        await use_case.execute(
            user_id=current_user_id,
            other_user_id=user_id,
        )

    return success_response({"message": "Conversation marked as seen"})
