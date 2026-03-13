from __future__ import annotations

import pytest

from fb.infrastructure.realtime.connection_manager import ConnectionManager


class FakeWebSocket:
    """Minimal WebSocket fake for unit testing."""

    def __init__(self) -> None:
        self.accepted: bool = False
        self.sent_messages: list[dict] = []
        self.closed: bool = False

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, data: dict) -> None:
        if self.closed:
            raise RuntimeError("Connection closed")
        self.sent_messages.append(data)


class TestConnectionManager:
    """Core ConnectionManager state and routing tests."""

    async def test_connect_registers_user(self) -> None:
        mgr = ConnectionManager()
        ws = FakeWebSocket()

        await mgr.connect("user-1", ws)

        assert ws.accepted
        assert mgr.is_online("user-1")
        assert "user-1" in mgr.get_online_users()

    async def test_disconnect_removes_user(self) -> None:
        mgr = ConnectionManager()
        ws = FakeWebSocket()

        await mgr.connect("user-1", ws)
        await mgr.disconnect("user-1", ws)

        assert not mgr.is_online("user-1")
        assert "user-1" not in mgr.get_online_users()

    async def test_disconnect_nonexistent_is_noop(self) -> None:
        mgr = ConnectionManager()
        ws = FakeWebSocket()

        # Should not raise
        await mgr.disconnect("ghost", ws)

    async def test_send_to_user_delivers_message(self) -> None:
        mgr = ConnectionManager()
        ws = FakeWebSocket()
        await mgr.connect("user-1", ws)

        await mgr.send_to_user("user-1", {"type": "hello"})

        assert ws.sent_messages == [{"type": "hello"}]

    async def test_send_to_user_skips_offline_user(self) -> None:
        mgr = ConnectionManager()

        # Should not raise
        await mgr.send_to_user("offline", {"type": "nope"})

    async def test_send_to_user_removes_dead_connections(self) -> None:
        mgr = ConnectionManager()
        alive = FakeWebSocket()
        dead = FakeWebSocket()
        dead.closed = True  # Will raise on send_json

        await mgr.connect("user-1", alive)
        await mgr.connect("user-1", dead)

        await mgr.send_to_user("user-1", {"type": "test"})

        assert alive.sent_messages == [{"type": "test"}]
        # Dead connection removed; alive still registered
        assert mgr.is_online("user-1")

    async def test_multiple_connections_per_user(self) -> None:
        mgr = ConnectionManager()
        ws1 = FakeWebSocket()
        ws2 = FakeWebSocket()

        await mgr.connect("user-1", ws1)
        await mgr.connect("user-1", ws2)

        await mgr.send_to_user("user-1", {"type": "msg"})

        assert ws1.sent_messages == [{"type": "msg"}]
        assert ws2.sent_messages == [{"type": "msg"}]

    async def test_disconnect_one_keeps_other(self) -> None:
        mgr = ConnectionManager()
        ws1 = FakeWebSocket()
        ws2 = FakeWebSocket()

        await mgr.connect("user-1", ws1)
        await mgr.connect("user-1", ws2)
        await mgr.disconnect("user-1", ws1)

        assert mgr.is_online("user-1")
        await mgr.send_to_user("user-1", {"type": "still here"})
        assert ws2.sent_messages == [{"type": "still here"}]

    async def test_is_online_false_when_not_connected(self) -> None:
        mgr = ConnectionManager()
        assert not mgr.is_online("nobody")

    async def test_get_online_users_returns_correct_set(self) -> None:
        mgr = ConnectionManager()
        ws1 = FakeWebSocket()
        ws2 = FakeWebSocket()

        await mgr.connect("alice", ws1)
        await mgr.connect("bob", ws2)

        assert mgr.get_online_users() == {"alice", "bob"}

    async def test_broadcast_sends_to_multiple_users(self) -> None:
        mgr = ConnectionManager()
        ws_a = FakeWebSocket()
        ws_b = FakeWebSocket()

        await mgr.connect("alice", ws_a)
        await mgr.connect("bob", ws_b)

        await mgr.broadcast(["alice", "bob"], {"type": "announcement"})

        assert ws_a.sent_messages == [{"type": "announcement"}]
        assert ws_b.sent_messages == [{"type": "announcement"}]

    async def test_all_dead_connections_cleans_up_user(self) -> None:
        mgr = ConnectionManager()
        dead = FakeWebSocket()
        dead.closed = True

        await mgr.connect("user-1", dead)
        await mgr.send_to_user("user-1", {"type": "test"})

        # User entry should be cleaned up after all connections are dead
        assert not mgr.is_online("user-1")
        assert "user-1" not in mgr.get_online_users()
