from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UploadInput:
    owner_id: str
    entity_id: str      # "post-uuid", "profile", etc.
    entity_type: str    # "post", "avatar", "cover", "chat"
    file_data: bytes
    filename: str
    content_type: str


@dataclass(frozen=True)
class MediaOutput:
    id: str
    owner_id: str
    entity_id: str
    entity_type: str
    original_url: str
    thumbnail_url: str | None
    processed_url: str | None
    media_type: str
    content_type: str
    file_size: int
    width: int | None
    height: int | None
    duration_seconds: float | None
    status: str
    created_at: str | None
    updated_at: str | None = None


@dataclass(frozen=True)
class DeleteMediaInput:
    media_id: str
    owner_id: str
