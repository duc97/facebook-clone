from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from fb.config import Settings
from fb.main import create_app

_FAKE_POST_ID = "550e8400-e29b-41d4-a716-446655440000"
_FAKE_SHARE_ID = "550e8400-e29b-41d4-a716-446655440001"


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


class TestReactionEndpointsAuth:
    """Test that reaction endpoints require authentication."""

    async def test_post_reaction_without_auth_returns_401(self, client: AsyncClient) -> None:
        response = await client.post(
            f"/api/v1/posts/{_FAKE_POST_ID}/reactions",
            json={"reaction_type": "LOVE"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False

    async def test_delete_reaction_without_auth_returns_401(self, client: AsyncClient) -> None:
        response = await client.delete(f"/api/v1/posts/{_FAKE_POST_ID}/reactions")
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False

    async def test_reaction_endpoint_exists(self, client: AsyncClient) -> None:
        """Verify the reactions endpoint exists (not 404/405 for the route itself)."""
        response = await client.post(
            f"/api/v1/posts/{_FAKE_POST_ID}/reactions",
            json={"reaction_type": "LOVE"},
        )
        # The route exists — returns 401 (auth), not 404 (not found) or 405 (method not allowed)
        assert response.status_code == 401


class TestShareEndpointsAuth:
    """Test that share endpoints require authentication."""

    async def test_post_share_without_auth_returns_401(self, client: AsyncClient) -> None:
        response = await client.post(
            f"/api/v1/posts/{_FAKE_POST_ID}/share",
            json={"content": "Check this out!"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False

    async def test_delete_share_without_auth_returns_401(self, client: AsyncClient) -> None:
        response = await client.delete(
            f"/api/v1/posts/{_FAKE_POST_ID}/shares/{_FAKE_SHARE_ID}"
        )
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False

    async def test_share_endpoint_exists(self, client: AsyncClient) -> None:
        """Verify the share endpoint exists (not 404/405 for the route itself)."""
        response = await client.post(
            f"/api/v1/posts/{_FAKE_POST_ID}/share",
            json={"content": "test"},
        )
        # The route exists — returns 401 (auth), not 404 or 405
        assert response.status_code == 401
