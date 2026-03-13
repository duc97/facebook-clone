from __future__ import annotations

from typing import Protocol, runtime_checkable

from fb.domain.media.entities import Media, MediaStatus
from fb.domain.shared.entity_id import EntityId


@runtime_checkable
class MediaRepository(Protocol):
    """Repository protocol for Media persistence."""

    async def save(self, media: Media) -> Media: ...

    async def find_by_id(self, media_id: EntityId) -> Media | None: ...

    async def find_by_owner(
        self,
        owner_id: EntityId,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Media]: ...

    async def update_status(
        self,
        media_id: EntityId,
        status: MediaStatus,
        processed_url: str | None = None,
        thumbnail_url: str | None = None,
        width: int | None = None,
        height: int | None = None,
    ) -> None: ...

    async def delete(self, media_id: EntityId) -> None: ...
