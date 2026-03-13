from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class PageInfo:
    has_next_page: bool
    has_previous_page: bool
    start_cursor: str | None = None
    end_cursor: str | None = None


@dataclass(frozen=True, slots=True)
class CursorPage(Generic[T]):
    items: tuple[T, ...]
    page_info: PageInfo
    total_count: int


def encode_cursor(created_at: datetime, entity_id: str) -> str:
    """Encode a created_at timestamp and entity ID into a cursor string."""
    raw = f"{created_at.isoformat()}:{entity_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    """Decode a cursor string into a created_at timestamp and entity ID."""
    raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    parts = raw.rsplit(":", 1)
    return datetime.fromisoformat(parts[0]), parts[1]
