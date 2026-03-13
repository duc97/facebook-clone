from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from fb.config import Settings
from fb.main import create_app


@pytest.fixture
def app():
    settings = Settings(
        database_url="postgresql+asyncpg://fb:fb_password@localhost:5432/facebook_clone_test",
        redis_url="redis://localhost:6379/1",
        jwt_secret_key="test-secret-key-for-e2e-testing",
        debug=True,
    )
    return create_app(settings)


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestFriendE2E:
    async def test_send_request_unauthenticated(self, client: AsyncClient) -> None:
        """Sending a friend request without auth returns 401."""
        response = await client.post(
            "/api/v1/friends/requests",
            json={"receiver_id": "550e8400-e29b-41d4-a716-446655440000"},
        )
        assert response.status_code == 401

    async def test_pending_requests_unauthenticated(self, client: AsyncClient) -> None:
        query = {
            "query": """
                {
                    pendingRequests {
                        id
                        senderId
                        receiverId
                        status
                    }
                }
            """
        }
        response = await client.post("/api/v1/graphql", json=query)
        assert response.status_code == 200
        data = response.json()
        result = data["data"]["pendingRequests"]
        assert result is None
