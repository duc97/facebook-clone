from __future__ import annotations

import json

import pytest
from unittest.mock import AsyncMock

from fb.infrastructure.realtime.pubsub import RedisPubSub


class TestRedisPubSub:
    """Core pub/sub tests — publish routing and channel naming."""

    async def test_publish_calls_redis_with_correct_channel(self) -> None:
        mock_redis = AsyncMock()
        mock_manager = AsyncMock()
        pubsub = RedisPubSub(mock_redis, mock_manager)

        message = {"type": "chat.message", "data": {"text": "hi"}}
        await pubsub.publish("user-42", message)

        mock_redis.publish.assert_awaited_once_with(
            "user:user-42",
            json.dumps(message),
        )

    async def test_channel_naming_pattern(self) -> None:
        mock_redis = AsyncMock()
        mock_manager = AsyncMock()
        pubsub = RedisPubSub(mock_redis, mock_manager)

        await pubsub.publish("abc-123", {"type": "test"})

        call_args = mock_redis.publish.call_args
        channel = call_args[0][0]
        assert channel == "user:abc-123"
        assert channel.startswith("user:")

    async def test_publish_serializes_message_as_json(self) -> None:
        mock_redis = AsyncMock()
        mock_manager = AsyncMock()
        pubsub = RedisPubSub(mock_redis, mock_manager)

        message = {"type": "notification", "data": {"count": 5}}
        await pubsub.publish("user-1", message)

        call_args = mock_redis.publish.call_args
        payload = call_args[0][1]
        assert json.loads(payload) == message
