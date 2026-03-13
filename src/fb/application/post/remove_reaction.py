from __future__ import annotations

from fb.domain.shared.entity_id import EntityId
from fb.domain.post.reaction_repository import ReactionRepository
from fb.domain.post.repository import PostRepository
from fb.domain.post.interaction_exceptions import ReactionNotFoundError
from fb.application.shared.interfaces import UnitOfWork
from fb.application.post.interaction_dtos import RemoveReactionInput


class RemoveReactionUseCase:
    def __init__(
        self,
        reaction_repo: ReactionRepository,
        post_repo: PostRepository,
        uow: UnitOfWork,
    ) -> None:
        self._reaction_repo = reaction_repo
        self._post_repo = post_repo
        self._uow = uow

    async def execute(self, input_data: RemoveReactionInput) -> None:
        post_id = EntityId.from_str(input_data.post_id)
        user_id = EntityId.from_str(input_data.user_id)

        # Find existing reaction
        reaction = await self._reaction_repo.find_by_post_and_user(post_id, user_id)
        if not reaction:
            raise ReactionNotFoundError("User has not reacted to this post")

        # Decrement like count on post
        post = await self._post_repo.find_by_id(post_id)
        if post:
            updated_post = post.decrement_like_count()
            await self._post_repo.update(updated_post)

        # Delete reaction
        await self._reaction_repo.delete(reaction.id)

        await self._uow.commit()
