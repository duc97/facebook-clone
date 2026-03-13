from __future__ import annotations

from fb.domain.shared.entity_id import EntityId
from fb.domain.post.reaction import Reaction, ReactionType
from fb.domain.post.reaction_repository import ReactionRepository
from fb.domain.post.repository import PostRepository
from fb.domain.post.exceptions import PostNotFoundError
from fb.domain.post.interaction_exceptions import AlreadyReactedError
from fb.application.shared.interfaces import UnitOfWork
from fb.application.post.interaction_dtos import ReactToPostInput, ReactionOutput


class ReactToPostUseCase:
    def __init__(
        self,
        reaction_repo: ReactionRepository,
        post_repo: PostRepository,
        uow: UnitOfWork,
    ) -> None:
        self._reaction_repo = reaction_repo
        self._post_repo = post_repo
        self._uow = uow

    async def execute(self, input_data: ReactToPostInput) -> ReactionOutput:
        post_id = EntityId.from_str(input_data.post_id)
        user_id = EntityId.from_str(input_data.user_id)
        reaction_type = ReactionType(input_data.reaction_type)

        # Ensure post exists
        post = await self._post_repo.find_by_id(post_id)
        if not post:
            raise PostNotFoundError(f"Post with id {input_data.post_id} not found")

        # Check for existing reaction
        existing = await self._reaction_repo.find_by_post_and_user(post_id, user_id)
        if existing:
            if existing.reaction_type == reaction_type:
                raise AlreadyReactedError(
                    "User has already reacted with this type"
                )
            # Different type: remove old, add new (update)
            await self._reaction_repo.delete(existing.id)
        else:
            # New reaction — increment like count
            updated_post = post.increment_like_count()
            await self._post_repo.update(updated_post)

        # Create new reaction
        reaction = Reaction.create(
            post_id=post_id,
            user_id=user_id,
            reaction_type=reaction_type,
        )
        saved = await self._reaction_repo.save(reaction)

        await self._uow.commit()

        return ReactionOutput(
            id=str(saved.id),
            post_id=str(saved.post_id),
            user_id=str(saved.user_id),
            reaction_type=saved.reaction_type.value,
            created_at=str(saved.created_at) if saved.created_at else None,
        )
