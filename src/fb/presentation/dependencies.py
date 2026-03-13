from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from fb.container import Container
from fb.domain.auth.exceptions import InvalidTokenError


def get_container(request: Request) -> Container:
    """Get the DI container from the app state."""
    return request.app.state.container


async def get_current_user_id(
    request: Request,
    container: Container = Depends(get_container),
) -> str:
    """Extract and validate the current user from the JWT token."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
        )

    token = auth_header[7:]

    # Check blacklist
    if await container.token_blacklist.is_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )

    try:
        payload = container.token_service.decode_access_token(token)
        return payload["sub"]
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
