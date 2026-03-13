"""Use case for deleting a media record."""
from __future__ import annotations

from fb.application.media.dtos import DeleteMediaInput
from fb.application.shared.interfaces import UnitOfWork
from fb.domain.media.exceptions import MediaNotFoundError, MediaOwnershipError
from fb.domain.media.repository import MediaRepository
from fb.domain.profile.services import FileStorage
from fb.domain.shared.entity_id import EntityId


class DeleteMediaUseCase:
    """Check ownership, remove from storage, and delete the DB record."""

    def __init__(
        self,
        media_repo: MediaRepository,
        file_storage: FileStorage,
        uow: UnitOfWork,
    ) -> None:
        self._media_repo = media_repo
        self._file_storage = file_storage
        self._uow = uow

    async def execute(self, inp: DeleteMediaInput) -> None:
        media_id = EntityId.from_str(inp.media_id)
        media = await self._media_repo.find_by_id(media_id)
        if media is None:
            raise MediaNotFoundError()

        # Verify ownership
        if str(media.owner_id) != inp.owner_id:
            raise MediaOwnershipError()

        # Remove original from storage (best-effort — do not fail on storage error)
        try:
            await self._file_storage.delete(media.original_url)
        except Exception:
            pass  # Storage deletion is non-critical; proceed to remove DB record

        # Remove DB record
        await self._media_repo.delete(media_id)
        await self._uow.commit()
