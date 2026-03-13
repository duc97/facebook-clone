from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fb.domain.shared.entity_id import EntityId

# ── Allowed media types ──────────────────────────────────────────────

ALLOWED_MEDIA_TYPES: frozenset[str] = frozenset({
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "video/mp4",
    "video/quicktime",
    "video/webm",
})

MAX_MEDIA_FILE_SIZE: int = 50 * 1024 * 1024  # 50 MB


# ── Exceptions ───────────────────────────────────────────────────────


class MediaError(Exception):
    def __init__(self, message: str = "Media error") -> None:
        self.message = message
        super().__init__(self.message)


class InvalidMediaTypeError(MediaError):
    def __init__(self, content_type: str) -> None:
        super().__init__(
            f"Invalid media type: {content_type}. "
            f"Allowed types: {', '.join(sorted(ALLOWED_MEDIA_TYPES))}"
        )


class MediaTooLargeError(MediaError):
    def __init__(self, file_size: int) -> None:
        super().__init__(
            f"File size {file_size} bytes exceeds maximum allowed size of {MAX_MEDIA_FILE_SIZE} bytes"
        )


# ── Entity ───────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class MediaAttachment:
    """Immutable value object representing a media file attached to a post."""

    id: EntityId
    post_id: EntityId
    url: str
    content_type: str
    file_size: int
    created_at: datetime | None = None

    @classmethod
    def create(
        cls,
        post_id: EntityId,
        url: str,
        content_type: str,
        file_size: int,
    ) -> MediaAttachment:
        """Create a new MediaAttachment after validating content_type and file_size."""
        if content_type not in ALLOWED_MEDIA_TYPES:
            raise InvalidMediaTypeError(content_type)
        if file_size > MAX_MEDIA_FILE_SIZE:
            raise MediaTooLargeError(file_size)

        return cls(
            id=EntityId.generate(),
            post_id=post_id,
            url=url,
            content_type=content_type,
            file_size=file_size,
        )
