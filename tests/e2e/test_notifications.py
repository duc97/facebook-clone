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


class TestNotificationEndpoints:
    @pytest.mark.asyncio
    async def test_get_notifications_without_auth_returns_401(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/notifications")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_unread_count_without_auth_returns_401(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/notifications/unread-count")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_mark_all_read_without_auth_returns_401(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/notifications/read-all")
        assert response.status_code == 401
