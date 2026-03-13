from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Generic, TypeVar

from fastapi.responses import JSONResponse

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class ErrorDetail:
    code: str  # e.g. "USER_NOT_FOUND"
    message: str
    details: dict[str, Any] | None = None
    trace_id: str = ""


@dataclass(frozen=True, slots=True)
class PaginationMeta:
    total: int
    limit: int
    page: int | None = None  # offset-based
    cursor: str | None = None  # cursor-based
    has_next: bool = False


@dataclass(frozen=True, slots=True)
class ApiResponse(Generic[T]):
    success: bool
    data: T | None = None
    error: ErrorDetail | None = None
    meta: PaginationMeta | None = None
    version: str = "1.0"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _serialize(obj: Any) -> Any:
    """Recursively convert dataclass instances to plain dicts."""
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    return obj


def success_response(
    data: Any,
    meta: PaginationMeta | None = None,
    status_code: int = 200,
) -> JSONResponse:
    envelope = ApiResponse(
        success=True,
        data=data,
        meta=meta,
    )
    return JSONResponse(
        status_code=status_code,
        content=_serialize(envelope),
    )


def error_response(
    code: str,
    message: str,
    status_code: int,
    details: dict[str, Any] | None = None,
    trace_id: str = "",
) -> JSONResponse:
    envelope = ApiResponse(
        success=False,
        error=ErrorDetail(
            code=code,
            message=message,
            details=details,
            trace_id=trace_id,
        ),
    )
    return JSONResponse(
        status_code=status_code,
        content=_serialize(envelope),
    )


def paginated_response(
    data: Any,
    total: int,
    limit: int,
    page: int | None = None,
    cursor: str | None = None,
    has_next: bool = False,
) -> JSONResponse:
    meta = PaginationMeta(
        total=total,
        limit=limit,
        page=page,
        cursor=cursor,
        has_next=has_next,
    )
    return success_response(data=data, meta=meta)
