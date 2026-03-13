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


class TestFeedGraphQLQueries:
    """Test GraphQL feed queries end-to-end."""

    @pytest.mark.asyncio
    async def test_feed_query_introspection_includes_feed_field(self, client: AsyncClient) -> None:
        """Should include feed field in query introspection."""
        introspection_query = """
        query IntrospectionQuery {
            __schema {
                queryType {
                    fields {
                        name
                        type {
                            name
                            kind
                        }
                    }
                }
            }
        }
        """

        response = await client.post(
            "/api/v1/graphql",
            json={"query": introspection_query}
        )

        assert response.status_code == 200
        data = response.json()

        query_fields = data["data"]["__schema"]["queryType"]["fields"]
        field_names = [field["name"] for field in query_fields]

        assert "feed" in field_names

    @pytest.mark.asyncio
    async def test_feed_query_introspection_has_correct_return_type(self, client: AsyncClient) -> None:
        """Should have correct return type for feed field."""
        introspection_query = """
        query IntrospectionQuery {
            __schema {
                queryType {
                    fields {
                        name
                        type {
                            name
                            kind
                        }
                    }
                }
            }
        }
        """

        response = await client.post(
            "/api/v1/graphql",
            json={"query": introspection_query}
        )

        assert response.status_code == 200
        data = response.json()

        query_fields = data["data"]["__schema"]["queryType"]["fields"]
        feed_field = next((f for f in query_fields if f["name"] == "feed"), None)

        assert feed_field is not None
        assert feed_field["type"]["name"] == "FeedResponse"

    @pytest.mark.asyncio
    async def test_feed_query_requires_authentication(self, client: AsyncClient) -> None:
        """Should return null for unauthenticated users."""
        query = """
        query {
            feed {
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
            json={"query": query}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["feed"] is None

    @pytest.mark.asyncio
    async def test_feed_query_accepts_pagination_parameters(self, client: AsyncClient) -> None:
        """Should accept limit and offset parameters for pagination."""
        query = """
        query {
            feed(limit: 10, offset: 5) {
                posts {
                    id
                }
                totalCount
                hasNextPage
            }
        }
        """

        # This should not cause a syntax error
        response = await client.post(
            "/api/v1/graphql",
            json={"query": query}
        )

        assert response.status_code == 200
        # Should return null due to no authentication, but query structure is valid
        data = response.json()
        assert data["data"]["feed"] is None