from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from fb.presentation.graphql.context import GraphQLContext
from fb.presentation.graphql.middleware import get_graphql_context
from fb.domain.auth.exceptions import InvalidTokenError


class TestGraphQLContext:
    def _make_container(self) -> MagicMock:
        return MagicMock()

    def test_is_authenticated_true(self) -> None:
        """is_authenticated returns True when user_id is set."""
        ctx = GraphQLContext(
            container=self._make_container(),
            current_user_id="user-123",
            current_user_email="test@test.com",
        )
        assert ctx.is_authenticated is True

    def test_is_authenticated_false(self) -> None:
        """is_authenticated returns False when user_id is None."""
        ctx = GraphQLContext(container=self._make_container())
        assert ctx.is_authenticated is False

    def test_req_returns_stored_request(self) -> None:
        """req property returns the stored _request."""
        mock_request = MagicMock()
        ctx = GraphQLContext(
            container=self._make_container(),
            request=mock_request,
        )
        assert ctx.req is mock_request

    def test_attributes(self) -> None:
        """Context stores all provided attributes."""
        container = self._make_container()
        ctx = GraphQLContext(
            container=container,
            current_user_id="uid",
            current_user_email="e@e.com",
        )
        assert ctx.container is container
        assert ctx.current_user_id == "uid"
        assert ctx.current_user_email == "e@e.com"


class TestGetGraphQLContext:
    def _make_request(self, auth_header: str | None = None) -> MagicMock:
        request = MagicMock()
        headers: dict[str, str] = {}
        if auth_header is not None:
            headers["authorization"] = auth_header
        request.headers.get = lambda key, default="": headers.get(key, default)
        return request

    def _make_container(
        self,
        is_blacklisted: bool = False,
        payload: dict | None = None,
        decode_error: Exception | None = None,
    ) -> MagicMock:
        container = MagicMock()
        container.token_blacklist = AsyncMock()
        container.token_blacklist.is_blacklisted = AsyncMock(return_value=is_blacklisted)

        if decode_error:
            container.token_service.decode_access_token.side_effect = decode_error
        elif payload:
            container.token_service.decode_access_token.return_value = payload
        return container

    async def test_no_auth_header(self) -> None:
        """Returns unauthenticated context when no Authorization header."""
        request = self._make_request()
        container = self._make_container()

        ctx = await get_graphql_context(request, container)

        assert ctx.is_authenticated is False
        assert ctx.current_user_id is None

    async def test_invalid_auth_prefix(self) -> None:
        """Returns unauthenticated context when header doesn't start with Bearer."""
        request = self._make_request(auth_header="Basic abc123")
        container = self._make_container()

        ctx = await get_graphql_context(request, container)

        assert ctx.is_authenticated is False

    async def test_blacklisted_token(self) -> None:
        """Returns unauthenticated context when token is blacklisted."""
        request = self._make_request(auth_header="Bearer blacklisted-token")
        container = self._make_container(is_blacklisted=True)

        ctx = await get_graphql_context(request, container)

        assert ctx.is_authenticated is False
        container.token_blacklist.is_blacklisted.assert_awaited_once_with("blacklisted-token")

    async def test_valid_token(self) -> None:
        """Returns authenticated context with valid token."""
        request = self._make_request(auth_header="Bearer valid-token")
        container = self._make_container(
            payload={"sub": "user-123", "email": "test@test.com"}
        )

        ctx = await get_graphql_context(request, container)

        assert ctx.is_authenticated is True
        assert ctx.current_user_id == "user-123"
        assert ctx.current_user_email == "test@test.com"

    async def test_invalid_token_decode_error(self) -> None:
        """Returns unauthenticated context when token decode fails."""
        request = self._make_request(auth_header="Bearer bad-token")
        container = self._make_container(
            decode_error=InvalidTokenError("expired")
        )

        ctx = await get_graphql_context(request, container)

        assert ctx.is_authenticated is False

    async def test_generic_exception(self) -> None:
        """Returns unauthenticated context on unexpected errors."""
        request = self._make_request(auth_header="Bearer crash-token")
        container = self._make_container(
            decode_error=Exception("unexpected")
        )

        ctx = await get_graphql_context(request, container)

        assert ctx.is_authenticated is False
