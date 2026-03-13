from __future__ import annotations

import asyncio
import json
import logging

from redis.asyncio import Redis

from fb.infrastructure.realtime.connection_manager import ConnectionManager

logger = logging.getLogger(__name__)


class RedisPubSub:
    """Redis pub/sub wrapper for cross-process WebSocket message delivery.

    Each user has a dedicated channel ``user:{user_id}``.  When a message is
    published to a user's channel the background listener forwards it to all
    local WebSocket connections for that user via the *ConnectionManager*.
    """

    def __init__(self, redis: Redis, connection_manager: ConnectionManager) -> None:
        self._redis = redis
        self._manager = connection_manager
        self._pubsub: object | None = None
        self._listener_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Subscribe to ``user:*`` pattern and start the listener loop."""
        self._pubsub = self._redis.pubsub()
        await self._pubsub.psubscribe("user:*")  # type: ignore[union-attr]
        self._listener_task = asyncio.create_task(self._listen())
        logger.info("RedisPubSub listener started")

    async def stop(self) -> None:
        """Cancel the listener and close the subscription."""
        if self._listener_task is not None:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        if self._pubsub is not None:
            await self._pubsub.unsubscribe()  # type: ignore[union-attr]
            await self._pubsub.close()  # type: ignore[union-attr]
        logger.info("RedisPubSub listener stopped")

    async def publish(self, user_id: str, message: dict) -> None:
        """Publish *message* to the ``user:{user_id}`` channel."""
        await self._redis.publish(f"user:{user_id}", json.dumps(message))

    async def _listen(self) -> None:
        """Background task that reads pub/sub messages and delivers them."""
        try:
            async for msg in self._pubsub.listen():  # type: ignore[union-attr]
                if msg["type"] != "pmessage":
                    continue
                channel = msg["channel"]
                if isinstance(channel, bytes):
                    channel = channel.decode()
                user_id = channel.split(":", 1)[1]
                data = json.loads(msg["data"])
                await self._manager.send_to_user(user_id, data)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("RedisPubSub listener crashed")
