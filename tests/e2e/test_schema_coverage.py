"""E2E tests for GraphQL queries and REST endpoints schema validation (no DB required)."""
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


class TestAuthSchemaE2E:
    """E2E tests for auth REST endpoints and GraphQL me query."""

    async def test_logout_unauthenticated(self, client: AsyncClient) -> None:
        """Logout without authentication returns 401."""
        response = await client.post("/api/v1/auth/logout")
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False

    async def test_me_unauthenticated(self, client: AsyncClient) -> None:
        """me query returns null when not authenticated."""
        query = {"query": "{ me { id email displayName } }"}
        response = await client.post("/api/v1/graphql", json=query)
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["me"] is None

    async def test_auth_register_unauthenticated(self, client: AsyncClient) -> None:
        """Register with invalid data returns 422."""
        response = await client.post("/api/v1/auth/register", json={})
        assert response.status_code == 422

    async def test_auth_login_endpoint_exists(self, client: AsyncClient) -> None:
        """Login with invalid data returns 422."""
        response = await client.post("/api/v1/auth/login", json={})
        assert response.status_code == 422


class TestFriendSchemaE2E:
    """E2E tests for friend REST endpoints and GraphQL queries."""

    async def test_friend_request_unauthenticated(self, client: AsyncClient) -> None:
        """Send friend request without authentication returns 401."""
        response = await client.post("/api/v1/friends/requests", json={})
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False

    async def test_mutual_friends_unauthenticated(self, client: AsyncClient) -> None:
        """mutualFriends returns null when not authenticated."""
        query = {
            "query": """
                {
                    mutualFriends(otherId: "550e8400-e29b-41d4-a716-446655440000") {
                        friendIds
                        totalCount
                    }
                }
            """
        }
        response = await client.post("/api/v1/graphql", json=query)
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["mutualFriends"] is None


class TestProfileQuerySchemaE2E:
    """E2E tests for profile GraphQL queries and REST endpoints."""

    async def test_profile_query_exists(self, client: AsyncClient) -> None:
        """Verify profile query fields exist."""
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
        assert "profile" in field_names
        assert "myProfile" in field_names
        assert "friends" in field_names
        assert "mutualFriends" in field_names

    async def test_my_profile_unauthenticated(self, client: AsyncClient) -> None:
        """myProfile returns null when not authenticated."""
        query = {"query": "{ myProfile { id bio } }"}
        response = await client.post("/api/v1/graphql", json=query)
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["myProfile"] is None

    async def test_profile_update_unauthenticated(self, client: AsyncClient) -> None:
        """Update profile without authentication returns 401."""
        response = await client.put(
            "/api/v1/users/fake-id/profile", json={"bio": "test"}
        )
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False


class TestPostSchemaE2E:
    """E2E tests for post-related GraphQL queries and REST endpoints."""

    async def test_post_create_unauthenticated_rest(self, client: AsyncClient) -> None:
        """Create post without authentication returns 401."""
        response = await client.post(
            "/api/v1/posts", json={"content": "hello"}
        )
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False

    async def test_post_query_exists(self, client: AsyncClient) -> None:
        """Verify post query fields exist."""
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
        assert "post" in field_names
        assert "postsByAuthor" in field_names
        assert "feed" in field_names
        assert "comments" in field_names

    async def test_post_type_schema(self, client: AsyncClient) -> None:
        """Verify PostType has expected fields."""
        query = {
            "query": """
                {
                    __type(name: "PostType") {
                        fields {
                            name
                            type {
                                name
                                kind
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
        assert "id" in field_names
        assert "authorId" in field_names
        assert "content" in field_names
        assert "mediaUrls" in field_names
        assert "likeCount" in field_names
        assert "commentCount" in field_names
        assert "isPublished" in field_names

    async def test_feed_response_type_schema(self, client: AsyncClient) -> None:
        """Verify FeedResponse has expected fields."""
        query = {
            "query": """
                {
                    __type(name: "FeedResponse") {
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
        assert "posts" in field_names
        assert "totalCount" in field_names
        assert "hasNextPage" in field_names
        assert "endCursor" in field_names
        assert "startCursor" in field_names

    async def test_create_post_unauthenticated(self, client: AsyncClient) -> None:
        """Create post via REST without authentication returns 401."""
        response = await client.post(
            "/api/v1/posts", json={"content": "hello"}
        )
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False

    async def test_update_post_unauthenticated(self, client: AsyncClient) -> None:
        """Update post via REST without authentication returns 401."""
        response = await client.put(
            "/api/v1/posts/550e8400-e29b-41d4-a716-446655440000",
            json={"content": "edited"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False

    async def test_delete_post_unauthenticated(self, client: AsyncClient) -> None:
        """Delete post via REST without authentication returns 401."""
        response = await client.delete(
            "/api/v1/posts/550e8400-e29b-41d4-a716-446655440000"
        )
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False

    async def test_feed_unauthenticated(self, client: AsyncClient) -> None:
        """feed returns null when not authenticated."""
        query = {
            "query": """
                {
                    feed(limit: 10) {
                        posts {
                            id
                            content
                        }
                        totalCount
                        hasNextPage
                    }
                }
            """
        }
        response = await client.post("/api/v1/graphql", json=query)
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["feed"] is None


class TestInteractionSchemaE2E:
    """E2E tests for interaction-related REST endpoints and GraphQL types."""

    async def test_interaction_endpoint_unauthenticated(self, client: AsyncClient) -> None:
        """Like post via REST without authentication returns 401."""
        response = await client.post("/api/v1/posts/fake-id/like")
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False

    async def test_comment_type_schema(self, client: AsyncClient) -> None:
        """Verify CommentType has expected fields."""
        query = {
            "query": """
                {
                    __type(name: "CommentType") {
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
        assert "id" in field_names
        assert "postId" in field_names
        assert "authorId" in field_names
        assert "content" in field_names
        assert "createdAt" in field_names

    def test_like_type_schema(self) -> None:
        """Verify LikeType has expected fields (via import — not exposed in query-only schema)."""
        from fb.presentation.graphql.types.interaction import LikeType

        field_names = [
            f.python_name for f in LikeType.__strawberry_definition__.fields
        ]
        assert "id" in field_names
        assert "post_id" in field_names
        assert "user_id" in field_names

    async def test_comments_response_type_schema(self, client: AsyncClient) -> None:
        """Verify CommentsResponse has expected fields."""
        query = {
            "query": """
                {
                    __type(name: "CommentsResponse") {
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
        assert "comments" in field_names
        assert "totalCount" in field_names
        assert "hasNextPage" in field_names

    async def test_create_comment_unauthenticated(self, client: AsyncClient) -> None:
        """Create comment via REST without authentication returns 401."""
        response = await client.post(
            "/api/v1/posts/550e8400-e29b-41d4-a716-446655440000/comments",
            json={"content": "test"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False

    async def test_delete_comment_unauthenticated(self, client: AsyncClient) -> None:
        """Delete comment via REST without authentication returns 401."""
        response = await client.delete(
            "/api/v1/posts/550e8400-e29b-41d4-a716-446655440000/comments/550e8400-e29b-41d4-a716-446655440001"
        )
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False

    async def test_like_post_unauthenticated(self, client: AsyncClient) -> None:
        """Like post via REST without authentication returns 401."""
        response = await client.post(
            "/api/v1/posts/550e8400-e29b-41d4-a716-446655440000/like"
        )
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False

    async def test_unlike_post_unauthenticated(self, client: AsyncClient) -> None:
        """Unlike post via REST without authentication returns 401."""
        response = await client.delete(
            "/api/v1/posts/550e8400-e29b-41d4-a716-446655440000/like"
        )
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
