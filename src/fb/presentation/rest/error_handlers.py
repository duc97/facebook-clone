from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from fb.presentation.rest.response import error_response

logger = logging.getLogger(__name__)

# ── Domain exception imports ──────────────────────────────────────────

from fb.domain.auth.exceptions import (
    AuthError,
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenBlacklistedError,
    UserInactiveError,
    UserNotFoundError,
)
from fb.domain.friend.exceptions import (
    AlreadyFriendsError,
    CannotFriendSelfError,
    FriendRequestAlreadyExistsError,
    FriendRequestNotFoundError,
    NotFriendsError,
    UserBlockedError,
)
from fb.domain.post.exceptions import (
    PostContentTooLongError,
    PostNotFoundError,
    PostPermissionError,
)
from fb.domain.post.interaction_exceptions import (
    AlreadyLikedError,
    AlreadyReactedError,
    AlreadySharedError,
    CannotShareOwnPostError,
    CommentNotFoundError,
    CommentPermissionError,
    NotLikedError,
    ReactionNotFoundError,
    ShareNotFoundError,
    SharePermissionError,
)
from fb.domain.profile.exceptions import (
    InvalidFileTypeError,
    ProfileNotFoundError,
)
from fb.domain.post.media import (
    InvalidMediaTypeError,
    MediaTooLargeError,
)
from fb.domain.notification.exceptions import (
    NotificationNotFoundError,
)
from fb.domain.media.exceptions import (
    InvalidMediaTypeError as MediaInvalidTypeError,
    MediaTooLargeError as MediaFileTooLargeError,
    MediaNotFoundError,
    MediaOwnershipError,
)
from fb.domain.chat.exceptions import (
    CannotMessageSelfError,
    ConversationNotFoundError,
    EmptyMessageError,
    MessageNotFoundError,
    MessageTooLongError,
)

# ── Mapping: exception class → (http_status, error_code) ─────────────

_EXCEPTION_MAP: dict[type[Exception], tuple[int, str]] = {
    InvalidCredentialsError: (401, "INVALID_CREDENTIALS"),
    InvalidTokenError: (401, "INVALID_TOKEN"),
    TokenBlacklistedError: (401, "TOKEN_BLACKLISTED"),
    AuthError: (401, "AUTH_ERROR"),
    UserInactiveError: (403, "USER_INACTIVE"),
    UserBlockedError: (403, "USER_BLOCKED"),
    PostPermissionError: (403, "POST_PERMISSION_DENIED"),
    CommentPermissionError: (403, "COMMENT_PERMISSION_DENIED"),
    SharePermissionError: (403, "SHARE_PERMISSION_DENIED"),
    UserNotFoundError: (404, "USER_NOT_FOUND"),
    PostNotFoundError: (404, "POST_NOT_FOUND"),
    CommentNotFoundError: (404, "COMMENT_NOT_FOUND"),
    ReactionNotFoundError: (404, "REACTION_NOT_FOUND"),
    ShareNotFoundError: (404, "SHARE_NOT_FOUND"),
    FriendRequestNotFoundError: (404, "FRIEND_REQUEST_NOT_FOUND"),
    ProfileNotFoundError: (404, "PROFILE_NOT_FOUND"),
    CannotFriendSelfError: (400, "CANNOT_FRIEND_SELF"),
    CannotShareOwnPostError: (400, "CANNOT_SHARE_OWN_POST"),
    EmailAlreadyExistsError: (409, "EMAIL_ALREADY_EXISTS"),
    AlreadyLikedError: (409, "ALREADY_LIKED"),
    AlreadyReactedError: (409, "ALREADY_REACTED"),
    AlreadySharedError: (409, "ALREADY_SHARED"),
    NotLikedError: (409, "NOT_LIKED"),
    FriendRequestAlreadyExistsError: (409, "FRIEND_REQUEST_EXISTS"),
    AlreadyFriendsError: (409, "ALREADY_FRIENDS"),
    NotFriendsError: (409, "NOT_FRIENDS"),
    PostContentTooLongError: (422, "POST_CONTENT_TOO_LONG"),
    InvalidFileTypeError: (422, "INVALID_FILE_TYPE"),
    InvalidMediaTypeError: (415, "INVALID_MEDIA_TYPE"),
    MediaTooLargeError: (413, "MEDIA_TOO_LARGE"),
    MediaInvalidTypeError: (415, "INVALID_MEDIA_TYPE"),
    MediaFileTooLargeError: (413, "MEDIA_TOO_LARGE"),
    MediaNotFoundError: (404, "MEDIA_NOT_FOUND"),
    MediaOwnershipError: (403, "MEDIA_OWNERSHIP_DENIED"),
    NotificationNotFoundError: (404, "NOTIFICATION_NOT_FOUND"),
    EmptyMessageError: (400, "EMPTY_MESSAGE"),
    MessageTooLongError: (422, "MESSAGE_TOO_LONG"),
    MessageNotFoundError: (404, "MESSAGE_NOT_FOUND"),
    ConversationNotFoundError: (404, "CONVERSATION_NOT_FOUND"),
    CannotMessageSelfError: (400, "CANNOT_MESSAGE_SELF"),
}


def _get_trace_id(request: Request) -> str:
    return request.headers.get("X-Request-ID", "")


# ── Handler factories ────────────────────────────────────────────────


async def _handle_domain_exception(request: Request, exc: Exception):  # noqa: ANN201
    """Look up the exception class in the mapping (most-specific first)."""
    for exc_cls in type(exc).__mro__:
        entry = _EXCEPTION_MAP.get(exc_cls)  # type: ignore[arg-type]
        if entry is not None:
            status_code, code = entry
            return error_response(
                code=code,
                message=str(exc),
                status_code=status_code,
                trace_id=_get_trace_id(request),
            )
    # Fallback — should never happen for mapped exceptions
    return error_response(
        code="INTERNAL_ERROR",
        message="An unexpected error occurred",
        status_code=500,
        trace_id=_get_trace_id(request),
    )


async def _handle_http_exception(request: Request, exc: HTTPException):  # noqa: ANN201
    return error_response(
        code="HTTP_ERROR",
        message=str(exc.detail),
        status_code=exc.status_code,
        trace_id=_get_trace_id(request),
    )


async def _handle_validation_error(request: Request, exc: RequestValidationError):  # noqa: ANN201
    details = {
        "errors": [
            {
                "loc": list(err.get("loc", [])),
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
            }
            for err in exc.errors()
        ]
    }
    return error_response(
        code="VALIDATION_ERROR",
        message="Request validation failed",
        status_code=422,
        details=details,
        trace_id=_get_trace_id(request),
    )


async def _handle_generic_exception(request: Request, exc: Exception):  # noqa: ANN201
    logger.exception("Unhandled exception", exc_info=exc)
    # Check debug flag from settings (attached to container)
    debug = False
    try:
        debug = request.app.state.container.settings.debug
    except Exception:
        pass

    message = str(exc) if debug else "An unexpected error occurred"
    return error_response(
        code="INTERNAL_ERROR",
        message=message,
        status_code=500,
        trace_id=_get_trace_id(request),
    )


# ── Registration ─────────────────────────────────────────────────────


def register_error_handlers(app: FastAPI) -> None:
    """Register all global exception handlers on the FastAPI application."""

    # Domain exceptions — register each concrete class so FastAPI
    # dispatches to the most-specific handler first.
    for exc_cls in _EXCEPTION_MAP:
        app.add_exception_handler(exc_cls, _handle_domain_exception)

    app.add_exception_handler(HTTPException, _handle_http_exception)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _handle_validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _handle_generic_exception)
