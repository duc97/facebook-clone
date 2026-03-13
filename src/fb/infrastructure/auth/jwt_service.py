from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from fb.config import Settings
from fb.domain.auth.exceptions import InvalidTokenError


class JWTTokenService:
    """JWT implementation of TokenService protocol."""

    def __init__(self, settings: Settings) -> None:
        self._secret = settings.jwt_secret_key
        self._algorithm = settings.jwt_algorithm
        self._access_expire_minutes = settings.jwt_access_token_expire_minutes
        self._refresh_expire_days = settings.jwt_refresh_token_expire_days

    def create_access_token(self, user_id: str, email: str) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_id,
            "email": email,
            "type": "access",
            "iat": now,
            "exp": now + timedelta(minutes=self._access_expire_minutes),
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def create_refresh_token(self, user_id: str) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_id,
            "type": "refresh",
            "iat": now,
            "exp": now + timedelta(days=self._refresh_expire_days),
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def decode_access_token(self, token: str) -> dict[str, str]:
        try:
            payload = jwt.decode(
                token, self._secret, algorithms=[self._algorithm]
            )
        except jwt.ExpiredSignatureError:
            raise InvalidTokenError("Access token has expired")
        except jwt.InvalidTokenError:
            raise InvalidTokenError("Invalid access token")

        if payload.get("type") != "access":
            raise InvalidTokenError("Token is not an access token")

        return {"sub": payload["sub"], "email": payload["email"]}

    def decode_refresh_token(self, token: str) -> dict[str, str]:
        try:
            payload = jwt.decode(
                token, self._secret, algorithms=[self._algorithm]
            )
        except jwt.ExpiredSignatureError:
            raise InvalidTokenError("Refresh token has expired")
        except jwt.InvalidTokenError:
            raise InvalidTokenError("Invalid refresh token")

        if payload.get("type") != "refresh":
            raise InvalidTokenError("Token is not a refresh token")

        return {"sub": payload["sub"]}
