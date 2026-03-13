from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

from fb.presentation.dependencies import get_container, get_current_user_id
from fb.domain.auth.exceptions import InvalidTokenError


class TestGetContainer:
    def test_returns_container_from_app_state(self) -> None:
        """get_container extracts container from request.app.state."""
        mock_container = MagicMock()
        mock_request = MagicMock()
        mock_request.app.state.container = mock_container

        result = get_container(mock_request)

        assert result is mock_container


class TestGetCurrentUserId:
    def _make_request(self, auth_header: str | None = None) -> MagicMock:
        request = MagicMock()
        headers: dict[str, str] = {}
        if auth_header is not None:
            headers["authorization"] = auth_header
        request.headers.get = lambda key, default="": headers.get(key, default)
        return request

    async def test_missing_auth_header_raises_401(self) -> None:
        """Raises 401 when no Authorization header."""
        request = self._make_request()
        container = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(request, container)

        assert exc_info.value.status_code == 401
        assert "Missing or invalid" in exc_info.value.detail

    async def test_non_bearer_header_raises_401(self) -> None:
        """Raises 401 when auth header doesn't start with Bearer."""
        request = self._make_request(auth_header="Basic abc")
        container = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(request, container)

        assert exc_info.value.status_code == 401

    async def test_blacklisted_token_raises_401(self) -> None:
        """Raises 401 when token is blacklisted."""
        request = self._make_request(auth_header="Bearer revoked-token")
        container = MagicMock()
        container.token_blacklist = AsyncMock()
        container.token_blacklist.is_blacklisted = AsyncMock(return_value=True)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(request, container)

        assert exc_info.value.status_code == 401
        assert "revoked" in exc_info.value.detail

    async def test_valid_token_returns_user_id(self) -> None:
        """Returns user ID from valid token payload."""
        request = self._make_request(auth_header="Bearer valid-token")
        container = MagicMock()
        container.token_blacklist = AsyncMock()
        container.token_blacklist.is_blacklisted = AsyncMock(return_value=False)
        container.token_service.decode_access_token.return_value = {"sub": "user-abc"}

        result = await get_current_user_id(request, container)

        assert result == "user-abc"

    async def test_invalid_token_raises_401(self) -> None:
        """Raises 401 when token decode fails."""
        request = self._make_request(auth_header="Bearer bad-token")
        container = MagicMock()
        container.token_blacklist = AsyncMock()
        container.token_blacklist.is_blacklisted = AsyncMock(return_value=False)
        container.token_service.decode_access_token.side_effect = InvalidTokenError("invalid")

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(request, container)

        assert exc_info.value.status_code == 401
