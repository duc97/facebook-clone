"""Use cases for retrieving media records."""
from __future__ import annotations

from fb.application.media.dtos import MediaOutput
from fb.domain.media.exceptions import MediaNotFoundError
from fb.domain.media.repository import MediaRepository
from fb.domain.shared.entity_id import EntityId
from fb.domain.media.entities import Media


class GetMediaUseCase:
    """Return a single media record by its ID."""

    def __init__(self, media_repo: MediaRepository) -> None:
        self._media_repo = media_repo

    async def execute(self, media_id: str) -> MediaOutput:
        media = await self._media_repo.find_by_id(EntityId.from_str(media_id))
        if media is None:
            raise MediaNotFoundError()
        return _to_output(media)


class GetEntityMediaUseCase:
    """Return all media records belonging to a given entity (post, profile, etc.)."""

    def __init__(self, media_repo: MediaRepository) -> None:
        self._media_repo = media_repo

    async def execute(self, entity_type: str, entity_id: str) -> list[MediaOutput]:
        media_list = await self._media_repo.find_by_entity(entity_type, entity_id)
        return [_to_output(m) for m in media_list]


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
