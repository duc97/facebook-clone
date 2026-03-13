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


SEARCH_USERS_QUERY = """
    query SearchUsers($query: String!, $limit: Int, $offset: Int) {
        searchUsers(query: $query, limit: $limit, offset: $offset) {
            users {
                id
                email
                displayName
                isActive
            }
            totalCount
            hasNextPage
        }
    }
"""


class TestSearchUsersGraphQL:
    async def test_search_users_schema_introspection(
        self, client: AsyncClient
    ) -> None:
        """Verify searchUsers field exists in schema via introspection."""
        query = {
            "query": """
                {
                    __type(name: "Query") {
                        fields {
                            name
                        }
                    }
                }
            """
        }
        response = await client.post("/api/v1/graphql", json=query)
        assert response.status_code == 200
        data = response.json()
        field_names = [f["name"] for f in data["data"]["__type"]["fields"]]
        assert "searchUsers" in field_names

    async def test_search_users_response_type_structure(
        self, client: AsyncClient
    ) -> None:
        """Verify UserSearchResponse type has correct fields."""
        query = {
            "query": """
                {
                    __type(name: "UserSearchResponse") {
                        fields {
                            name
                            type {
                                kind
                                name
                            }
                        }
                    }
                }
            """
        }
        response = await client.post("/api/v1/graphql", json=query)
        assert response.status_code == 200
        data = response.json()
        field_names = [f["name"] for f in data["data"]["__type"]["fields"]]
        assert "users" in field_names
        assert "totalCount" in field_names
        assert "hasNextPage" in field_names
