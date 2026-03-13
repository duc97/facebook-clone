from __future__ import annotations

from fb.domain.shared.entity_id import EntityId
from fb.domain.post.share_repository import ShareRepository
from fb.domain.post.interaction_exceptions import ShareNotFoundError, SharePermissionError
from fb.application.shared.interfaces import UnitOfWork
from fb.application.post.interaction_dtos import DeleteShareInput


class DeleteShareUseCase:
    def __init__(
        self,
        share_repo: ShareRepository,
        uow: UnitOfWork,
    ) -> None:
        self._share_repo = share_repo
        self._uow = uow

    async def execute(self, input_data: DeleteShareInput) -> None:
        share_id = EntityId.from_str(input_data.share_id)
        user_id = EntityId.from_str(input_data.user_id)

        # Find share
        share = await self._share_repo.find_by_id(share_id)
        if not share:
            raise ShareNotFoundError(f"Share with id {input_data.share_id} not found")

        # Only the sharer can delete
        if share.user_id != user_id:
            raise SharePermissionError("Only the sharer can delete this share")

        # Delete share
        await self._share_repo.delete(share_id)

        await self._uow.commit()
