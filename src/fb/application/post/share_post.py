from __future__ import annotations

from fb.domain.shared.entity_id import EntityId
from fb.domain.post.share import Share
from fb.domain.post.share_repository import ShareRepository
from fb.domain.post.repository import PostRepository
from fb.domain.post.exceptions import PostNotFoundError
from fb.domain.post.interaction_exceptions import CannotShareOwnPostError
from fb.application.shared.interfaces import UnitOfWork
from fb.application.post.interaction_dtos import SharePostInput, ShareOutput


class SharePostUseCase:
    def __init__(
        self,
        share_repo: ShareRepository,
        post_repo: PostRepository,
        uow: UnitOfWork,
    ) -> None:
        self._share_repo = share_repo
        self._post_repo = post_repo
        self._uow = uow

    async def execute(self, input_data: SharePostInput) -> ShareOutput:
        post_id = EntityId.from_str(input_data.post_id)
        user_id = EntityId.from_str(input_data.user_id)

        # Ensure post exists
        post = await self._post_repo.find_by_id(post_id)
        if not post:
            raise PostNotFoundError(f"Post with id {input_data.post_id} not found")

        # Cannot share own post
        if post.author_id == user_id:
            raise CannotShareOwnPostError("You cannot share your own post")

        # Create share
        share = Share.create(
            post_id=post_id,
            user_id=user_id,
            content=input_data.content,
        )
        saved = await self._share_repo.save(share)

        await self._uow.commit()

        return ShareOutput(
            id=str(saved.id),
            post_id=str(saved.post_id),
            user_id=str(saved.user_id),
            content=saved.content,
            created_at=str(saved.created_at) if saved.created_at else None,
        )
