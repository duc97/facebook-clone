"""Image post-processing use case: run after initial upload."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from fb.domain.media.entities import MediaStatus, MediaType
from fb.domain.media.repository import MediaRepository
from fb.domain.profile.services import FileStorage
from fb.domain.shared.entity_id import EntityId

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessImageInput:
    media_id: str
    image_data: bytes
    content_type: str


class ProcessImageUseCase:
    """Resize/compress image + generate thumbnail, then update media record."""

    def __init__(
        self,
        media_repo: MediaRepository,
        file_storage: FileStorage,
    ) -> None:
        self._media_repo = media_repo
        self._file_storage = file_storage

    async def execute(self, inp: ProcessImageInput) -> None:
        from fb.infrastructure.media.image_processor import ImageProcessor

        media_id = EntityId.from_str(inp.media_id)
        processor = ImageProcessor()

        if not processor.is_available():
            # Mark as READY with original URL if Pillow not installed
            await self._media_repo.update_status(media_id, MediaStatus.READY)
            return

        # Mark as PROCESSING
        await self._media_repo.update_status(media_id, MediaStatus.PROCESSING)

        try:
            loop = asyncio.get_event_loop()

            # Run CPU-bound processing in thread pool
            processed = await loop.run_in_executor(
                None, processor.process, inp.image_data, inp.content_type
            )
            thumbnail = await loop.run_in_executor(
                None, processor.generate_thumbnail, inp.image_data, inp.content_type
            )

            # Upload processed versions
            proc_filename = f"images/processed/{inp.media_id}.webp"
            thumb_filename = f"images/thumbnails/{inp.media_id}.webp"

            processed_url = await self._file_storage.upload(
                file_data=processed.data,
                filename=proc_filename,
                content_type=processed.content_type,
            )
            thumbnail_url = await self._file_storage.upload(
                file_data=thumbnail.data,
                filename=thumb_filename,
                content_type=thumbnail.content_type,
            )

            # Update DB record
            await self._media_repo.update_status(
                media_id=media_id,
                status=MediaStatus.READY,
                processed_url=processed_url,
                thumbnail_url=thumbnail_url,
                width=processed.width,
                height=processed.height,
            )

        except Exception:
            logger.exception("Image processing failed for media_id=%s", inp.media_id)
            await self._media_repo.update_status(media_id, MediaStatus.FAILED)
