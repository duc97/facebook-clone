from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from fb.domain.shared.entity_id import EntityId


class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


class MediaStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Media:
    """Media domain entity — represents an uploaded file with processing state."""

    id: EntityId
    owner_id: EntityId
    entity_id: str
    entity_type: str          # post | avatar | cover | chat
    original_url: str
    thumbnail_url: str | None
    processed_url: str | None
    media_type: MediaType
    content_type: str
    file_size: int
    width: int | None
    height: int | None
    duration_seconds: float | None
    status: MediaStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def create(
        cls,
        owner_id: EntityId,
        entity_id: str,
        entity_type: str,
        original_url: str,
        media_type: MediaType,
        content_type: str,
        file_size: int,
        width: int | None = None,
        height: int | None = None,
        duration_seconds: float | None = None,
    ) -> Media:
        """Factory method: create a new Media record in PENDING status."""
        return cls(
            id=EntityId.generate(),
            owner_id=owner_id,
            entity_id=entity_id,
            entity_type=entity_type,
            original_url=original_url,
            thumbnail_url=None,
            processed_url=None,
            media_type=media_type,
            content_type=content_type,
            file_size=file_size,
            width=width,
            height=height,
            duration_seconds=duration_seconds,
            status=MediaStatus.PENDING,
        )

    def mark_processing(self) -> Media:
        """Return new Media with PROCESSING status."""
        return Media(
            id=self.id,
            owner_id=self.owner_id,
            entity_id=self.entity_id,
            entity_type=self.entity_type,
            original_url=self.original_url,
            thumbnail_url=self.thumbnail_url,
            processed_url=self.processed_url,
            media_type=self.media_type,
            content_type=self.content_type,
            file_size=self.file_size,
            width=self.width,
            height=self.height,
            duration_seconds=self.duration_seconds,
            status=MediaStatus.PROCESSING,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    def mark_ready(
        self,
        processed_url: str | None = None,
        thumbnail_url: str | None = None,
        width: int | None = None,
        height: int | None = None,
    ) -> Media:
        """Return new Media with READY status and optional processed metadata."""
        return Media(
            id=self.id,
            owner_id=self.owner_id,
            entity_id=self.entity_id,
            entity_type=self.entity_type,
            original_url=self.original_url,
            thumbnail_url=thumbnail_url or self.thumbnail_url,
            processed_url=processed_url or self.processed_url,
            media_type=self.media_type,
            content_type=self.content_type,
            file_size=self.file_size,
            width=width or self.width,
            height=height or self.height,
            duration_seconds=self.duration_seconds,
            status=MediaStatus.READY,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    def mark_failed(self) -> Media:
        """Return new Media with FAILED status."""
        return Media(
            id=self.id,
            owner_id=self.owner_id,
            entity_id=self.entity_id,
            entity_type=self.entity_type,
            original_url=self.original_url,
            thumbnail_url=self.thumbnail_url,
            processed_url=self.processed_url,
            media_type=self.media_type,
            content_type=self.content_type,
            file_size=self.file_size,
            width=self.width,
            height=self.height,
            duration_seconds=self.duration_seconds,
            status=MediaStatus.FAILED,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
