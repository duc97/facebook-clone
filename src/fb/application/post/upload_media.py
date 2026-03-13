from __future__ import annotations

import uuid
from dataclasses import dataclass

from fb.domain.post.media import (
    ALLOWED_MEDIA_TYPES,
    MAX_MEDIA_FILE_SIZE,
    InvalidMediaTypeError,
    MediaTooLargeError,
)
from fb.domain.profile.services import FileStorage


# ── DTOs ─────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class UploadMediaInput:
    post_id: str
    file_data: bytes
    filename: str
    content_type: str


@dataclass(frozen=True, slots=True)
class MediaOutput:
    url: str
    content_type: str
    file_size: int


# ── Use Case ─────────────────────────────────────────────────────────


class UploadMediaUseCase:
    """Validate a media file and upload it to the configured storage backend."""

    def __init__(self, file_storage: FileStorage) -> None:
        self._file_storage = file_storage

    async def execute(self, input_data: UploadMediaInput) -> MediaOutput:
        # Validate content type
        if input_data.content_type not in ALLOWED_MEDIA_TYPES:
            raise InvalidMediaTypeError(input_data.content_type)

        # Validate file size
        file_size = len(input_data.file_data)
        if file_size > MAX_MEDIA_FILE_SIZE:
            raise MediaTooLargeError(file_size)

        # Generate unique filename preserving extension
        extension = _extract_extension(input_data.filename)
        unique_filename = f"{uuid.uuid4()}{extension}"

        # Delegate to storage backend
        url = await self._file_storage.upload(
            file_data=input_data.file_data,
            filename=unique_filename,
            content_type=input_data.content_type,
        )

        return MediaOutput(
            url=url,
            content_type=input_data.content_type,
            file_size=file_size,
        )


def _extract_extension(filename: str) -> str:
    """Return the file extension including the dot, or empty string."""
    dot_index = filename.rfind(".")
    if dot_index == -1:
        return ""
    return filename[dot_index:]
