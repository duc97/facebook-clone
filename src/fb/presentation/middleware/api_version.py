from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_DEFAULT_VERSION = "1.0"


class APIVersionMiddleware(BaseHTTPMiddleware):
    """Reads the ``API-Version`` request header and stores it on
    ``request.state.api_version`` for downstream consumers."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        api_version = request.headers.get("API-Version", _DEFAULT_VERSION)
        request.state.api_version = api_version
        return await call_next(request)
