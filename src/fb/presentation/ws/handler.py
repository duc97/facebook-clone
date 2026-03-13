from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from fb.container import Container
from fb.domain.auth.exceptions import InvalidTokenError

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Main WebSocket endpoint.

    Authenticates via query parameter: ``/api/v1/ws?token=<jwt>``
    """
    container: Container = websocket.app.state.container

    # --- Auth from query param ---
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    try:
        if await container.token_blacklist.is_blacklisted(token):
            await websocket.close(code=4001, reason="Token revoked")
            return
        payload = container.token_service.decode_access_token(token)
        user_id: str = payload["sub"]
    except (InvalidTokenError, Exception):
        await websocket.close(code=4001, reason="Invalid token")
        return

    # --- Register connection ---
    manager = container.connection_manager
    await manager.connect(user_id, websocket)
    await _broadcast_presence(container, user_id, online=True)

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = data.get("type")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg_type == "chat.send":
                await _handle_chat_message(container, user_id, data)
            elif msg_type == "chat.typing":
                await _handle_typing(container, user_id, data)
            elif msg_type == "chat.seen":
                await _handle_seen(container, user_id, data)
            else:
                await websocket.send_json(
                    {"type": "error", "message": f"Unknown type: {msg_type}"}
                )
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket error for user %s", user_id)
    finally:
        await _broadcast_presence(container, user_id, online=False)
        await manager.disconnect(user_id, websocket)


async def _handle_chat_message(container: Container, sender_id: str, data: dict) -> None:
    """Process an incoming chat message and deliver it via pub/sub."""
    from fb.application.chat.dtos import SendMessageInput
    from fb.application.chat.send_message import SendMessageUseCase
    from fb.infrastructure.repositories.message_repo import SqlAlchemyMessageRepository

    receiver_id = data.get("receiver_id", "")
    content = data.get("content", "")

    if not receiver_id or not content:
        return

    uow = container.create_uow()
    async with uow:
        msg_repo = SqlAlchemyMessageRepository(uow.session)
        use_case = SendMessageUseCase(message_repo=msg_repo, uow=uow)
        result = await use_case.execute(
            SendMessageInput(sender_id=sender_id, receiver_id=receiver_id, content=content)
        )

    outgoing = {
        "type": "chat.message",
        "data": {
            "id": result.id,
            "sender_id": result.sender_id,
            "receiver_id": result.receiver_id,
            "content": result.content,
            "created_at": result.created_at,
        },
    }
    await container.pubsub.publish(receiver_id, outgoing)
    await container.pubsub.publish(sender_id, outgoing)


async def _handle_typing(container: Container, sender_id: str, data: dict) -> None:
    """Forward a typing indicator to the receiver."""
    receiver_id = data.get("receiver_id", "")
    if not receiver_id:
        return
    await container.pubsub.publish(
        receiver_id,
        {
            "type": "chat.typing",
            "data": {"sender_id": sender_id, "is_typing": data.get("is_typing", True)},
        },
    )


async def _handle_seen(container: Container, sender_id: str, data: dict) -> None:
    """Mark a message as seen and notify the original sender."""
    from fb.domain.shared.entity_id import EntityId
    from fb.infrastructure.repositories.message_repo import SqlAlchemyMessageRepository

    message_id = data.get("message_id", "")
    receiver_id = data.get("receiver_id", "")

    if not message_id:
        return

    uow = container.create_uow()
    async with uow:
        msg_repo = SqlAlchemyMessageRepository(uow.session)
        await msg_repo.mark_seen(EntityId.from_str(message_id))
        await uow.commit()

    if receiver_id:
        await container.pubsub.publish(
            receiver_id,
            {
                "type": "chat.seen",
                "data": {"message_id": message_id, "seen_by": sender_id},
            },
        )


async def _broadcast_presence(container: Container, user_id: str, online: bool) -> None:
    """Notify all friends of the user about their online/offline status."""
    from fb.domain.shared.entity_id import EntityId
    from fb.infrastructure.repositories.friend_repo import SqlAlchemyFriendRepository

    event_type = "user.online" if online else "user.offline"
    event = {"type": event_type, "data": {"user_id": user_id}}

    try:
        async with container.session_factory() as session:
            friend_repo = SqlAlchemyFriendRepository(session)
            # Fetch all friends without pagination (presence is time-sensitive)
            friend_ids = await friend_repo.get_friends(
                EntityId.from_str(user_id), limit=5000, offset=0
            )

        for friend_id in friend_ids:
            await container.pubsub.publish(str(friend_id.value), event)
    except Exception:
        logger.exception("Failed to broadcast presence for user %s", user_id)
