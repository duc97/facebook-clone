from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from fb.config import Settings

logger = logging.getLogger(__name__)

_SKIP_PATHS: frozenset[str] = frozenset({"/health", "/ready"})


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-based sliding-window rate limiter.

    Determines the caller role from the presence of a valid JWT
    (authenticated → "user", otherwise → "guest"). Premium is reserved
    for future role-based expansion.

    If Redis is unavailable the request is allowed through (fail-open).
    """

    def __init__(self, app, settings: Settings) -> None:  # noqa: ANN001
        super().__init__(app)
        self._limits: dict[str, int] = {
            "guest": settings.rate_limit_guest,
            "user": settings.rate_limit_user,
            "premium": settings.rate_limit_premium,
        }
        self._window: int = 60  # seconds

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        role = self._resolve_role(request)
        identifier = self._resolve_identifier(request, role)
        limit = self._limits[role]

        allowed, remaining, reset_at = await self._check_rate_limit(
            request, identifier, limit
        )

        if not allowed:
            return self._rate_limit_response(limit, reset_at)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_at)
        return response

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_role(request: Request) -> str:
        """Return 'user' if a valid-looking Authorization bearer token is
        present, otherwise 'guest'. Full JWT validation is not performed
        here — downstream auth dependencies handle that."""
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer ") and len(auth_header) > 7:
            return "user"
        return "guest"

    @staticmethod
    def _resolve_identifier(request: Request, role: str) -> str:
        """Build an identifier for the rate-limit bucket."""
        if role == "guest":
            forwarded = request.headers.get("X-Forwarded-For")
            ip = forwarded.split(",")[0].strip() if forwarded else (
                request.client.host if request.client else "unknown"
            )
            return f"guest:{ip}"
        # For authenticated users, use the raw token as a stable key
        token = request.headers.get("Authorization", "")[7:]
        return f"user:{token[:32]}"

    async def _check_rate_limit(
        self,
        request: Request,
        identifier: str,
        limit: int,
    ) -> tuple[bool, int, int]:
        """Return (allowed, remaining, reset_timestamp).

        Uses a simple sliding-window counter stored in Redis.
        Falls back to allowing the request if Redis is unreachable.
        """
        now = int(time.time())
        window_key = now // self._window
        reset_at = (window_key + 1) * self._window
        redis_key = f"rate_limit:{identifier}:{window_key}"

        try:
            redis = request.app.state.container.redis
            current = await redis.incr(redis_key)
            if current == 1:
                await redis.expire(redis_key, self._window + 1)
            remaining = max(0, limit - current)
            return current <= limit, remaining, reset_at
        except Exception:
            logger.warning("Rate limiter Redis unavailable — allowing request")
            return True, limit, reset_at

    @staticmethod
    def _rate_limit_response(limit: int, reset_at: int) -> JSONResponse:
        body = {
            "success": False,
            "data": None,
            "error": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": f"Rate limit of {limit} requests per minute exceeded",
                "details": None,
                "trace_id": "",
            },
            "meta": None,
            "version": "1.0",
        }
        return JSONResponse(
            status_code=429,
            content=body,
            headers={
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_at),
                "Retry-After": str(reset_at - int(time.time())),
            },
        )
