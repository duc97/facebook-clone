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


class TestHealthEndpoints:
    async def test_health(self, client: AsyncClient) -> None:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    async def test_ready(self, client: AsyncClient) -> None:
        response = await client.get("/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}


class TestGraphQLEndpoint:
    async def test_graphql_health_query(self, client: AsyncClient) -> None:
        query = {"query": "{ health }"}
        response = await client.post("/api/v1/graphql", json=query)
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["health"] == "ok"

    async def test_graphql_me_unauthenticated(self, client: AsyncClient) -> None:
        query = {"query": "{ me { id email displayName } }"}
        response = await client.post("/api/v1/graphql", json=query)
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["me"] is None
