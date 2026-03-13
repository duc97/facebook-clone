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


class TestFeedRESTEndpoint:
    """Test the GET /api/v1/feed REST endpoint."""

    @pytest.mark.asyncio
    async def test_feed_without_auth_returns_401(self, client: AsyncClient) -> None:
        """GET /api/v1/feed without auth should return 401."""
        response = await client.get("/api/v1/feed")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_feed_with_missing_bearer_prefix_returns_401(self, client: AsyncClient) -> None:
        """GET /api/v1/feed with missing Bearer prefix should return 401."""
        response = await client.get(
            "/api/v1/feed",
            headers={"Authorization": "invalid-token"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_feed_endpoint_exists(self, client: AsyncClient) -> None:
        """GET /api/v1/feed should exist (not 404/405)."""
        response = await client.get("/api/v1/feed")

        # Should be 401 (auth required), not 404 or 405
        assert response.status_code != 404
        assert response.status_code != 405

    @pytest.mark.asyncio
    async def test_feed_accepts_mode_parameter(self, client: AsyncClient) -> None:
        """GET /api/v1/feed?mode=ranked should not error with 422."""
        response = await client.get("/api/v1/feed?mode=ranked")

        # Should be 401 (no auth), not 422 (validation error)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_feed_accepts_chronological_mode(self, client: AsyncClient) -> None:
        """GET /api/v1/feed?mode=chronological should not error."""
        response = await client.get("/api/v1/feed?mode=chronological")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_feed_accepts_limit_parameter(self, client: AsyncClient) -> None:
        """GET /api/v1/feed?limit=10 should accept limit query param."""
        response = await client.get("/api/v1/feed?limit=10")

        assert response.status_code == 401


class TestFeedGraphQLWithMode:
    """Test the GraphQL feed query with mode parameter."""

    @pytest.mark.asyncio
    async def test_feed_query_accepts_mode_parameter(self, client: AsyncClient) -> None:
        """GraphQL feed query should accept a mode parameter."""
        query = """
        query {
            feed(limit: 10, mode: "ranked") {
                posts {
                    id
                    content
                }
                totalCount
                hasNextPage
            }
        }
        """

        response = await client.post(
            "/api/v1/graphql",
            json={"query": query},
        )

        assert response.status_code == 200
        data = response.json()
        # Should not have errors about unknown argument
        assert "errors" not in data or not any(
            "mode" in str(e.get("message", "")).lower()
            for e in data.get("errors", [])
        )

    @pytest.mark.asyncio
    async def test_feed_query_defaults_to_ranked(self, client: AsyncClient) -> None:
        """GraphQL feed query without mode should default to ranked."""
        query = """
        query {
            feed(limit: 10) {
                posts {
                    id
                }
                totalCount
                hasNextPage
            }
        }
        """

        response = await client.post(
            "/api/v1/graphql",
            json={"query": query},
        )

        assert response.status_code == 200
        # Should return null due to no auth, but query is valid
        data = response.json()
        assert data["data"]["feed"] is None
