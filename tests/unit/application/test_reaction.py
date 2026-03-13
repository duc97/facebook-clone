from __future__ import annotations

import pytest
from dataclasses import replace

from fb.domain.shared.entity_id import EntityId
from fb.domain.post.reaction import Reaction, ReactionType
from fb.domain.post.share import Share
from fb.domain.post.entities import Post
from fb.domain.post.exceptions import PostNotFoundError
from fb.domain.post.interaction_exceptions import (
    AlreadyReactedError,
    ReactionNotFoundError,
    CannotShareOwnPostError,
    ShareNotFoundError,
)
from fb.application.post.interaction_dtos import (
    ReactToPostInput,
    RemoveReactionInput,
    ReactionOutput,
    SharePostInput,
    DeleteShareInput,
    ShareOutput,
)
from fb.application.post.react_post import ReactToPostUseCase
from fb.application.post.remove_reaction import RemoveReactionUseCase
from fb.application.post.share_post import SharePostUseCase
from fb.application.post.delete_share import DeleteShareUseCase


# ── Test Fakes ──────────────────────────────────────────────────────────


class FakeReactionRepo:
    def __init__(self) -> None:
        self._reactions: dict[str, Reaction] = {}

    async def find_by_post_and_user(
        self, post_id: EntityId, user_id: EntityId
    ) -> Reaction | None:
        for r in self._reactions.values():
            if r.post_id == post_id and r.user_id == user_id:
                return r
        return None

    async def save(self, reaction: Reaction) -> Reaction:
        self._reactions[str(reaction.id)] = reaction
        return reaction

    async def delete(self, reaction_id: EntityId) -> None:
        self._reactions.pop(str(reaction_id), None)

    async def find_by_post(
        self, post_id: EntityId, limit: int = 20, offset: int = 0
    ) -> list[Reaction]:
        matching = [r for r in self._reactions.values() if r.post_id == post_id]
        return matching[offset : offset + limit]

    async def count_by_post(self, post_id: EntityId) -> int:
        return sum(1 for r in self._reactions.values() if r.post_id == post_id)

    async def count_by_type(self, post_id: EntityId) -> dict[ReactionType, int]:
        counts: dict[ReactionType, int] = {}
        for r in self._reactions.values():
            if r.post_id == post_id:
                counts[r.reaction_type] = counts.get(r.reaction_type, 0) + 1
        return counts


class FakeShareRepo:
    def __init__(self) -> None:
        self._shares: dict[str, Share] = {}

    async def find_by_id(self, share_id: EntityId) -> Share | None:
        return self._shares.get(str(share_id))

    async def save(self, share: Share) -> Share:
        self._shares[str(share.id)] = share
        return share

    async def delete(self, share_id: EntityId) -> None:
        self._shares.pop(str(share_id), None)

    async def find_by_post(
        self, post_id: EntityId, limit: int = 20, offset: int = 0
    ) -> list[Share]:
        matching = [s for s in self._shares.values() if s.post_id == post_id]
        return matching[offset : offset + limit]

    async def count_by_post(self, post_id: EntityId) -> int:
        return sum(1 for s in self._shares.values() if s.post_id == post_id)


class FakePostRepo:
    def __init__(self, posts: dict[str, Post] | None = None) -> None:
        self._posts = posts or {}

    async def find_by_id(self, post_id: EntityId) -> Post | None:
        return self._posts.get(str(post_id))

    async def update(self, post: Post) -> Post:
        self._posts[str(post.id)] = post
        return post


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


# ── Helper ──────────────────────────────────────────────────────────────


def _make_post(
    post_id: EntityId | None = None,
    author_id: EntityId | None = None,
) -> Post:
    author = author_id or EntityId.generate()
    post = Post.create(author_id=author, content="Test post")
    if post_id is not None:
        post = replace(post, id=post_id)
    return post


# ── ReactToPost Tests ───────────────────────────────────────────────────


class TestReactToPostUseCase:
    async def test_react_to_post_successfully(self) -> None:
        post_id = EntityId.generate()
        user_id = EntityId.generate()
        author_id = EntityId.generate()
        post = _make_post(post_id=post_id, author_id=author_id)

        reaction_repo = FakeReactionRepo()
        post_repo = FakePostRepo({str(post_id): post})
        uow = FakeUnitOfWork()

        use_case = ReactToPostUseCase(reaction_repo, post_repo, uow)
        input_data = ReactToPostInput(
            post_id=str(post_id),
            user_id=str(user_id),
            reaction_type="LOVE",
        )

        result = await use_case.execute(input_data)

        assert isinstance(result, ReactionOutput)
        assert result.post_id == str(post_id)
        assert result.user_id == str(user_id)
        assert result.reaction_type == "LOVE"
        assert result.id is not None
        assert uow.committed

    async def test_react_with_invalid_type_raises_error(self) -> None:
        post_id = EntityId.generate()
        user_id = EntityId.generate()
        post = _make_post(post_id=post_id)

        reaction_repo = FakeReactionRepo()
        post_repo = FakePostRepo({str(post_id): post})
        uow = FakeUnitOfWork()

        use_case = ReactToPostUseCase(reaction_repo, post_repo, uow)
        input_data = ReactToPostInput(
            post_id=str(post_id),
            user_id=str(user_id),
            reaction_type="INVALID",
        )

        with pytest.raises(ValueError):
            await use_case.execute(input_data)

        assert not uow.committed

    async def test_already_reacted_same_type_raises_error(self) -> None:
        post_id = EntityId.generate()
        user_id = EntityId.generate()
        post = _make_post(post_id=post_id)

        existing = Reaction.create(
            post_id=post_id, user_id=user_id, reaction_type=ReactionType.LOVE
        )

        reaction_repo = FakeReactionRepo()
        await reaction_repo.save(existing)
        post_repo = FakePostRepo({str(post_id): post})
        uow = FakeUnitOfWork()

        use_case = ReactToPostUseCase(reaction_repo, post_repo, uow)
        input_data = ReactToPostInput(
            post_id=str(post_id),
            user_id=str(user_id),
            reaction_type="LOVE",
        )

        with pytest.raises(AlreadyReactedError):
            await use_case.execute(input_data)

        assert not uow.committed

    async def test_react_different_type_updates_reaction(self) -> None:
        post_id = EntityId.generate()
        user_id = EntityId.generate()
        post = _make_post(post_id=post_id)

        existing = Reaction.create(
            post_id=post_id, user_id=user_id, reaction_type=ReactionType.LIKE
        )

        reaction_repo = FakeReactionRepo()
        await reaction_repo.save(existing)
        post_repo = FakePostRepo({str(post_id): post})
        uow = FakeUnitOfWork()

        use_case = ReactToPostUseCase(reaction_repo, post_repo, uow)
        input_data = ReactToPostInput(
            post_id=str(post_id),
            user_id=str(user_id),
            reaction_type="LOVE",
        )

        result = await use_case.execute(input_data)

        assert result.reaction_type == "LOVE"
        assert uow.committed

        # Verify old reaction was removed
        updated = await reaction_repo.find_by_post_and_user(post_id, user_id)
        assert updated is not None
        assert updated.reaction_type == ReactionType.LOVE

    async def test_react_post_not_found_raises_error(self) -> None:
        post_id = EntityId.generate()
        user_id = EntityId.generate()

        reaction_repo = FakeReactionRepo()
        post_repo = FakePostRepo()
        uow = FakeUnitOfWork()

        use_case = ReactToPostUseCase(reaction_repo, post_repo, uow)
        input_data = ReactToPostInput(
            post_id=str(post_id),
            user_id=str(user_id),
            reaction_type="LIKE",
        )

        with pytest.raises(PostNotFoundError):
            await use_case.execute(input_data)

        assert not uow.committed

    async def test_react_increments_like_count(self) -> None:
        post_id = EntityId.generate()
        user_id = EntityId.generate()
        post = _make_post(post_id=post_id)
        initial_count = post.like_count

        reaction_repo = FakeReactionRepo()
        post_repo = FakePostRepo({str(post_id): post})
        uow = FakeUnitOfWork()

        use_case = ReactToPostUseCase(reaction_repo, post_repo, uow)
        input_data = ReactToPostInput(
            post_id=str(post_id),
            user_id=str(user_id),
            reaction_type="LIKE",
        )

        await use_case.execute(input_data)

        updated_post = await post_repo.find_by_id(post_id)
        assert updated_post is not None
        assert updated_post.like_count == initial_count + 1


# ── RemoveReaction Tests ────────────────────────────────────────────────


class TestRemoveReactionUseCase:
    async def test_remove_reaction_successfully(self) -> None:
        post_id = EntityId.generate()
        user_id = EntityId.generate()
        post = _make_post(post_id=post_id)
        post = post.increment_like_count()

        reaction = Reaction.create(
            post_id=post_id, user_id=user_id, reaction_type=ReactionType.LIKE
        )

        reaction_repo = FakeReactionRepo()
        await reaction_repo.save(reaction)
        post_repo = FakePostRepo({str(post_id): post})
        uow = FakeUnitOfWork()

        use_case = RemoveReactionUseCase(reaction_repo, post_repo, uow)
        input_data = RemoveReactionInput(
            post_id=str(post_id),
            user_id=str(user_id),
        )

        await use_case.execute(input_data)

        remaining = await reaction_repo.find_by_post_and_user(post_id, user_id)
        assert remaining is None
        assert uow.committed

    async def test_remove_non_existent_reaction_raises_error(self) -> None:
        post_id = EntityId.generate()
        user_id = EntityId.generate()

        reaction_repo = FakeReactionRepo()
        post_repo = FakePostRepo()
        uow = FakeUnitOfWork()

        use_case = RemoveReactionUseCase(reaction_repo, post_repo, uow)
        input_data = RemoveReactionInput(
            post_id=str(post_id),
            user_id=str(user_id),
        )

        with pytest.raises(ReactionNotFoundError):
            await use_case.execute(input_data)

        assert not uow.committed

    async def test_remove_reaction_decrements_like_count(self) -> None:
        post_id = EntityId.generate()
        user_id = EntityId.generate()
        post = _make_post(post_id=post_id).increment_like_count()
        initial_count = post.like_count

        reaction = Reaction.create(
            post_id=post_id, user_id=user_id, reaction_type=ReactionType.LOVE
        )

        reaction_repo = FakeReactionRepo()
        await reaction_repo.save(reaction)
        post_repo = FakePostRepo({str(post_id): post})
        uow = FakeUnitOfWork()

        use_case = RemoveReactionUseCase(reaction_repo, post_repo, uow)
        input_data = RemoveReactionInput(
            post_id=str(post_id),
            user_id=str(user_id),
        )

        await use_case.execute(input_data)

        updated_post = await post_repo.find_by_id(post_id)
        assert updated_post is not None
        assert updated_post.like_count == initial_count - 1


# ── SharePost Tests ─────────────────────────────────────────────────────


class TestSharePostUseCase:
    async def test_share_post_successfully(self) -> None:
        post_id = EntityId.generate()
        author_id = EntityId.generate()
        sharer_id = EntityId.generate()
        post = _make_post(post_id=post_id, author_id=author_id)

        share_repo = FakeShareRepo()
        post_repo = FakePostRepo({str(post_id): post})
        uow = FakeUnitOfWork()

        use_case = SharePostUseCase(share_repo, post_repo, uow)
        input_data = SharePostInput(
            post_id=str(post_id),
            user_id=str(sharer_id),
            content="Check this out!",
        )

        result = await use_case.execute(input_data)

        assert isinstance(result, ShareOutput)
        assert result.post_id == str(post_id)
        assert result.user_id == str(sharer_id)
        assert result.content == "Check this out!"
        assert result.id is not None
        assert uow.committed

    async def test_share_post_with_empty_content(self) -> None:
        post_id = EntityId.generate()
        author_id = EntityId.generate()
        sharer_id = EntityId.generate()
        post = _make_post(post_id=post_id, author_id=author_id)

        share_repo = FakeShareRepo()
        post_repo = FakePostRepo({str(post_id): post})
        uow = FakeUnitOfWork()

        use_case = SharePostUseCase(share_repo, post_repo, uow)
        input_data = SharePostInput(
            post_id=str(post_id),
            user_id=str(sharer_id),
        )

        result = await use_case.execute(input_data)

        assert result.content == ""

    async def test_share_own_post_raises_error(self) -> None:
        author_id = EntityId.generate()
        post_id = EntityId.generate()
        post = _make_post(post_id=post_id, author_id=author_id)

        share_repo = FakeShareRepo()
        post_repo = FakePostRepo({str(post_id): post})
        uow = FakeUnitOfWork()

        use_case = SharePostUseCase(share_repo, post_repo, uow)
        input_data = SharePostInput(
            post_id=str(post_id),
            user_id=str(author_id),  # same as author
        )

        with pytest.raises(CannotShareOwnPostError):
            await use_case.execute(input_data)

        assert not uow.committed

    async def test_share_non_existent_post_raises_error(self) -> None:
        post_id = EntityId.generate()
        user_id = EntityId.generate()

        share_repo = FakeShareRepo()
        post_repo = FakePostRepo()
        uow = FakeUnitOfWork()

        use_case = SharePostUseCase(share_repo, post_repo, uow)
        input_data = SharePostInput(
            post_id=str(post_id),
            user_id=str(user_id),
        )

        with pytest.raises(PostNotFoundError):
            await use_case.execute(input_data)

        assert not uow.committed


# ── DeleteShare Tests ───────────────────────────────────────────────────


class TestDeleteShareUseCase:
    async def test_delete_share_successfully(self) -> None:
        share_id = EntityId.generate()
        user_id = EntityId.generate()
        post_id = EntityId.generate()

        share = Share(
            id=share_id,
            post_id=post_id,
            user_id=user_id,
            content="Shared!",
        )

        share_repo = FakeShareRepo()
        await share_repo.save(share)
        uow = FakeUnitOfWork()

        use_case = DeleteShareUseCase(share_repo, uow)
        input_data = DeleteShareInput(share_id=str(share_id), user_id=str(user_id))

        await use_case.execute(input_data)

        deleted = await share_repo.find_by_id(share_id)
        assert deleted is None
        assert uow.committed

    async def test_delete_non_existent_share_raises_error(self) -> None:
        share_id = EntityId.generate()
        user_id = EntityId.generate()

        share_repo = FakeShareRepo()
        uow = FakeUnitOfWork()

        use_case = DeleteShareUseCase(share_repo, uow)
        input_data = DeleteShareInput(share_id=str(share_id), user_id=str(user_id))

        with pytest.raises(ShareNotFoundError):
            await use_case.execute(input_data)

        assert not uow.committed

    async def test_delete_another_users_share_raises_permission_error(self) -> None:
        share_id = EntityId.generate()
        owner_id = EntityId.generate()
        other_user_id = EntityId.generate()
        post_id = EntityId.generate()

        share = Share(
            id=share_id,
            post_id=post_id,
            user_id=owner_id,
            content="Shared!",
        )

        share_repo = FakeShareRepo()
        await share_repo.save(share)
        uow = FakeUnitOfWork()

        use_case = DeleteShareUseCase(share_repo, uow)
        input_data = DeleteShareInput(share_id=str(share_id), user_id=str(other_user_id))

        from fb.domain.post.interaction_exceptions import SharePermissionError

        with pytest.raises(SharePermissionError):
            await use_case.execute(input_data)

        assert not uow.committed
