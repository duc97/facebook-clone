"""Generic media upload use case: validate → upload to S3 → persist record."""
from __future__ import annotations

import uuid

from fb.application.media.dtos import MediaOutput, UploadInput
from fb.application.shared.interfaces import UnitOfWork
from fb.domain.media.entities import Media, MediaType
from fb.domain.media.exceptions import InvalidMediaTypeError, MediaTooLargeError
from fb.domain.media.repository import MediaRepository
from fb.domain.profile.services import FileStorage
from fb.domain.shared.entity_id import EntityId

# Allowed MIME → MediaType mapping
_MIME_TO_TYPE: dict[str, MediaType] = {
    "image/jpeg": MediaType.IMAGE,
    "image/png": MediaType.IMAGE,
    "image/gif": MediaType.IMAGE,
    "image/webp": MediaType.IMAGE,
    "video/mp4": MediaType.VIDEO,
    "video/quicktime": MediaType.VIDEO,
    "video/webm": MediaType.VIDEO,
}

IMAGE_MAX_SIZE = 10 * 1024 * 1024  # 10 MB per image
VIDEO_MAX_SIZE = 50 * 1024 * 1024  # 50 MB per video


class UploadUseCase:
    def __init__(
        self,
        media_repo: MediaRepository,
        file_storage: FileStorage,
        uow: UnitOfWork,
    ) -> None:
        self._media_repo = media_repo
        self._file_storage = file_storage
        self._uow = uow

    async def execute(self, inp: UploadInput) -> MediaOutput:
        # 1. Validate MIME type
        media_type = _MIME_TO_TYPE.get(inp.content_type)
        if media_type is None:
            raise InvalidMediaTypeError(inp.content_type)

        # 2. Validate file size
        file_size = len(inp.file_data)
        max_size = IMAGE_MAX_SIZE if media_type == MediaType.IMAGE else VIDEO_MAX_SIZE
        if file_size > max_size:
            raise MediaTooLargeError(file_size, max_size)

        # 3. Build unique filename: <folder>/<uuid><ext>
        ext = _get_ext(inp.filename)
        folder = "images" if media_type == MediaType.IMAGE else "videos"
        unique_filename = f"{folder}/{uuid.uuid4()}{ext}"

        # 4. Upload to storage
        original_url = await self._file_storage.upload(
            file_data=inp.file_data,
            filename=unique_filename,
            content_type=inp.content_type,
        )

        # 5. Persist record
        media = Media.create(
            owner_id=EntityId.from_str(inp.owner_id),
            entity_id=inp.entity_id,
            entity_type=inp.entity_type,
            original_url=original_url,
            media_type=media_type,
            content_type=inp.content_type,
            file_size=file_size,
        )
        saved = await self._media_repo.save(media)
        await self._uow.commit()
        return _to_output(saved)


def _get_ext(filename: str) -> str:
    i = filename.rfind(".")
    return filename[i:] if i != -1 else ""


def _to_output(m: Media) -> MediaOutput:
    return MediaOutput(
        id=str(m.id),
        owner_id=str(m.owner_id),
        entity_id=m.entity_id,
        entity_type=m.entity_type,
        original_url=m.original_url,
        thumbnail_url=m.thumbnail_url,
        processed_url=m.processed_url,
        media_type=m.media_type.value,
        content_type=m.content_type,
        file_size=m.file_size,
        width=m.width,
        height=m.height,
        duration_seconds=m.duration_seconds,
        status=m.status.value,
        created_at=m.created_at.isoformat() if m.created_at else None,
        updated_at=m.updated_at.isoformat() if m.updated_at else None,
    )
