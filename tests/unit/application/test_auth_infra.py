from __future__ import annotations

import pytest

from fb.config import Settings
from fb.infrastructure.auth.password import BcryptPasswordHasher
from fb.infrastructure.auth.jwt_service import JWTTokenService
from fb.domain.auth.exceptions import InvalidTokenError


# ─── Password Hasher Tests ──────────────────────────────


class TestBcryptPasswordHasher:
    def setup_method(self) -> None:
        self.hasher = BcryptPasswordHasher()

    def test_hash_returns_string(self) -> None:
        result = self.hasher.hash("password123")
        assert isinstance(result, str)
        assert result != "password123"

    def test_hash_produces_different_hashes(self) -> None:
        h1 = self.hasher.hash("password123")
        h2 = self.hasher.hash("password123")
        assert h1 != h2  # Different salts

    def test_verify_correct_password(self) -> None:
        hashed = self.hasher.hash("mypassword")
        assert self.hasher.verify("mypassword", hashed) is True

    def test_verify_wrong_password(self) -> None:
        hashed = self.hasher.hash("mypassword")
        assert self.hasher.verify("wrongpassword", hashed) is False

    def test_hash_starts_with_bcrypt_prefix(self) -> None:
        hashed = self.hasher.hash("test")
        assert hashed.startswith("$2b$")


# ─── JWT Token Service Tests ────────────────────────────


class TestJWTTokenService:
    def setup_method(self) -> None:
        self.settings = Settings(
            database_url="postgresql+asyncpg://test",
            redis_url="redis://test",
            jwt_secret_key="test-secret-key-for-jwt",
            jwt_algorithm="HS256",
            jwt_access_token_expire_minutes=15,
            jwt_refresh_token_expire_days=7,
        )
        self.service = JWTTokenService(self.settings)

    def test_create_access_token(self) -> None:
        token = self.service.create_access_token(
            user_id="user-123", email="test@example.com"
        )
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_refresh_token(self) -> None:
        token = self.service.create_refresh_token(user_id="user-123")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_access_token(self) -> None:
        token = self.service.create_access_token(
            user_id="user-123", email="test@example.com"
        )
        payload = self.service.decode_access_token(token)
        assert payload["sub"] == "user-123"
        assert payload["email"] == "test@example.com"

    def test_decode_refresh_token(self) -> None:
        token = self.service.create_refresh_token(user_id="user-123")
        payload = self.service.decode_refresh_token(token)
        assert payload["sub"] == "user-123"

    def test_decode_access_token_invalid(self) -> None:
        with pytest.raises(InvalidTokenError):
            self.service.decode_access_token("invalid.token.here")

    def test_decode_refresh_token_invalid(self) -> None:
        with pytest.raises(InvalidTokenError):
            self.service.decode_refresh_token("invalid.token.here")

    def test_access_token_cannot_be_used_as_refresh(self) -> None:
        token = self.service.create_access_token(
            user_id="user-123", email="test@example.com"
        )
        with pytest.raises(InvalidTokenError, match="not a refresh token"):
            self.service.decode_refresh_token(token)

    def test_refresh_token_cannot_be_used_as_access(self) -> None:
        token = self.service.create_refresh_token(user_id="user-123")
        with pytest.raises(InvalidTokenError, match="not an access token"):
            self.service.decode_access_token(token)

    def test_different_secret_fails_decode(self) -> None:
        other_settings = Settings(
            database_url="postgresql+asyncpg://test",
            redis_url="redis://test",
            jwt_secret_key="different-secret",
        )
        other_service = JWTTokenService(other_settings)
        token = self.service.create_access_token(
            user_id="user-123", email="test@example.com"
        )
        with pytest.raises(InvalidTokenError):
            other_service.decode_access_token(token)

    def test_expired_access_token(self) -> None:
        expired_settings = Settings(
            database_url="postgresql+asyncpg://test",
            redis_url="redis://test",
            jwt_secret_key="test-secret-key-for-jwt",
            jwt_access_token_expire_minutes=0,  # Expire immediately
        )
        expired_service = JWTTokenService(expired_settings)
        # With 0 minutes, the token might be valid for a brief moment
        # Let's use negative to ensure expiry (JWT library handles this)
        import time
        from datetime import datetime, timedelta, timezone
        import jwt as pyjwt

        now = datetime.now(timezone.utc)
        payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "type": "access",
            "iat": now - timedelta(hours=1),
            "exp": now - timedelta(minutes=1),
        }
        token = pyjwt.encode(payload, "test-secret-key-for-jwt", algorithm="HS256")
        with pytest.raises(InvalidTokenError, match="expired"):
            self.service.decode_access_token(token)
