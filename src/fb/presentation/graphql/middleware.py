from __future__ import annotations

from starlette.requests import Request

from fb.container import Container
from fb.domain.auth.exceptions import InvalidTokenError
from fb.presentation.graphql.context import GraphQLContext


async def get_graphql_context(
    request: Request,
    container: Container,
) -> GraphQLContext:
    """Extract user info from JWT token in Authorization header."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return GraphQLContext(container=container, request=request)

    token = auth_header[7:]  # Strip "Bearer "

    # Check if token is blacklisted
    if await container.token_blacklist.is_blacklisted(token):
        return GraphQLContext(container=container, request=request)

    try:
        payload = container.token_service.decode_access_token(token)
        return GraphQLContext(
            container=container,
            current_user_id=payload["sub"],
            current_user_email=payload["email"],
            request=request,
        )
    except (InvalidTokenError, Exception):
        return GraphQLContext(container=container, request=request)
