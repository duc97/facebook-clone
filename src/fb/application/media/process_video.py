"""Video post-processing use case: extract metadata + thumbnail."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from fb.domain.media.entities import MediaStatus
from fb.domain.media.repository import MediaRepository
from fb.domain.profile.services import FileStorage
from fb.domain.shared.entity_id import EntityId

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessVideoInput:
    media_id: str
    video_data: bytes
    content_type: str


class ProcessVideoUseCase:
    """Extract video metadata and thumbnail, then update media record."""

    def __init__(
        self,
        media_repo: MediaRepository,
        file_storage: FileStorage,
    ) -> None:
        self._media_repo = media_repo
        self._file_storage = file_storage

    async def execute(self, inp: ProcessVideoInput) -> None:
        from fb.infrastructure.media.video_processor import VideoProcessor

        media_id = EntityId.from_str(inp.media_id)
        processor = VideoProcessor()

        if not processor.is_available():
            # ffmpeg not installed — mark as READY without processing
            await self._media_repo.update_status(media_id, MediaStatus.READY)
            return

        await self._media_repo.update_status(media_id, MediaStatus.PROCESSING)

        try:
            loop = asyncio.get_event_loop()

            # Run CPU-bound work in thread pool
            metadata = await loop.run_in_executor(
                None, processor.get_metadata, inp.video_data
            )
            thumbnail = await loop.run_in_executor(
                None, processor.extract_thumbnail, inp.video_data, 1.0
            )

            # Upload thumbnail if extracted
            thumbnail_url: str | None = None
            if thumbnail is not None and thumbnail.data:
                ext = ".webp" if thumbnail.content_type == "image/webp" else ".jpg"
                thumb_filename = f"videos/thumbnails/{inp.media_id}{ext}"
                thumbnail_url = await self._file_storage.upload(
                    file_data=thumbnail.data,
                    filename=thumb_filename,
                    content_type=thumbnail.content_type,
                )

            # Update record with metadata
            await self._media_repo.update_status(
                media_id=media_id,
                status=MediaStatus.READY,
                processed_url=None,   # original video IS the processed version
                thumbnail_url=thumbnail_url,
                width=metadata.width if metadata else None,
                height=metadata.height if metadata else None,
                duration_seconds=metadata.duration_seconds if metadata else None,
            )

        except Exception:
            logger.exception("Video processing failed for media_id=%s", inp.media_id)
            await self._media_repo.update_status(media_id, MediaStatus.FAILED)
