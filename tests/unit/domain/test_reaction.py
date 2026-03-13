from __future__ import annotations

import pytest

from fb.domain.shared.entity_id import EntityId
from fb.domain.post.reaction import Reaction, ReactionType
from fb.domain.post.share import Share
from fb.domain.post.interaction_exceptions import (
    AlreadyReactedError,
    ReactionNotFoundError,
    AlreadySharedError,
    ShareNotFoundError,
    CannotShareOwnPostError,
    InteractionError,
)


class TestReactionType:
    def test_all_reaction_types_exist(self) -> None:
        expected = {"LIKE", "LOVE", "HAHA", "WOW", "SAD", "ANGRY"}
        actual = {rt.value for rt in ReactionType}
        assert actual == expected

    def test_reaction_type_string_conversion(self) -> None:
        assert ReactionType.LIKE.value == "LIKE"
        assert ReactionType.LOVE.value == "LOVE"
        assert ReactionType.HAHA.value == "HAHA"
        assert ReactionType.WOW.value == "WOW"
        assert ReactionType.SAD.value == "SAD"
        assert ReactionType.ANGRY.value == "ANGRY"

    def test_reaction_type_from_string(self) -> None:
        assert ReactionType("LIKE") == ReactionType.LIKE
        assert ReactionType("LOVE") == ReactionType.LOVE

    def test_invalid_reaction_type_raises_error(self) -> None:
        with pytest.raises(ValueError):
            ReactionType("INVALID")


class TestReaction:
    def test_create_reaction_with_valid_data(self) -> None:
        post_id = EntityId.generate()
        user_id = EntityId.generate()

        reaction = Reaction.create(
            post_id=post_id,
            user_id=user_id,
            reaction_type=ReactionType.LOVE,
        )

        assert reaction.post_id == post_id
        assert reaction.user_id == user_id
        assert reaction.reaction_type == ReactionType.LOVE
        assert reaction.id is not None
        assert reaction.created_at is None  # Set by infrastructure

    def test_create_reaction_with_all_types(self) -> None:
        post_id = EntityId.generate()
        user_id = EntityId.generate()

        for rt in ReactionType:
            reaction = Reaction.create(
                post_id=post_id,
                user_id=user_id,
                reaction_type=rt,
            )
            assert reaction.reaction_type == rt

    def test_reaction_is_frozen(self) -> None:
        post_id = EntityId.generate()
        user_id = EntityId.generate()

        reaction = Reaction.create(
            post_id=post_id,
            user_id=user_id,
            reaction_type=ReactionType.LIKE,
        )

        with pytest.raises(AttributeError):
            reaction.reaction_type = ReactionType.LOVE  # type: ignore

    def test_reaction_has_unique_id(self) -> None:
        post_id = EntityId.generate()
        user_id = EntityId.generate()

        r1 = Reaction.create(post_id=post_id, user_id=user_id, reaction_type=ReactionType.LIKE)
        r2 = Reaction.create(post_id=post_id, user_id=user_id, reaction_type=ReactionType.LIKE)

        assert r1.id != r2.id


class TestShare:
    def test_create_share_with_valid_data(self) -> None:
        post_id = EntityId.generate()
        user_id = EntityId.generate()

        share = Share.create(
            post_id=post_id,
            user_id=user_id,
            content="Check this out!",
        )

        assert share.post_id == post_id
        assert share.user_id == user_id
        assert share.content == "Check this out!"
        assert share.id is not None
        assert share.created_at is None  # Set by infrastructure

    def test_create_share_with_empty_content(self) -> None:
        post_id = EntityId.generate()
        user_id = EntityId.generate()

        share = Share.create(post_id=post_id, user_id=user_id)

        assert share.content == ""

    def test_share_is_frozen(self) -> None:
        post_id = EntityId.generate()
        user_id = EntityId.generate()

        share = Share.create(post_id=post_id, user_id=user_id, content="Hello")

        with pytest.raises(AttributeError):
            share.content = "New content"  # type: ignore

    def test_share_has_unique_id(self) -> None:
        post_id = EntityId.generate()
        user_id = EntityId.generate()

        s1 = Share.create(post_id=post_id, user_id=user_id)
        s2 = Share.create(post_id=post_id, user_id=user_id)

        assert s1.id != s2.id


class TestReactionExceptions:
    def test_already_reacted_error(self) -> None:
        error = AlreadyReactedError("Already reacted")
        assert isinstance(error, InteractionError)
        assert error.message == "Already reacted"

    def test_reaction_not_found_error(self) -> None:
        error = ReactionNotFoundError("Reaction not found")
        assert isinstance(error, InteractionError)
        assert error.message == "Reaction not found"

    def test_already_shared_error(self) -> None:
        error = AlreadySharedError("Already shared")
        assert isinstance(error, InteractionError)
        assert error.message == "Already shared"

    def test_share_not_found_error(self) -> None:
        error = ShareNotFoundError("Share not found")
        assert isinstance(error, InteractionError)
        assert error.message == "Share not found"

    def test_cannot_share_own_post_error(self) -> None:
        error = CannotShareOwnPostError("Cannot share own post")
        assert isinstance(error, InteractionError)
        assert error.message == "Cannot share own post"


class TestReactionRepository:
    def test_reaction_repository_is_protocol(self) -> None:
        from fb.domain.post.reaction_repository import ReactionRepository

        assert hasattr(ReactionRepository, '_is_protocol')
        assert hasattr(ReactionRepository, '_is_runtime_protocol')

    def test_reaction_repository_has_required_methods(self) -> None:
        from fb.domain.post.reaction_repository import ReactionRepository

        required_methods = [
            'save',
            'find_by_post_and_user',
            'delete',
            'find_by_post',
            'count_by_post',
            'count_by_type',
        ]

        for method_name in required_methods:
            assert hasattr(ReactionRepository, method_name)
            method = getattr(ReactionRepository, method_name)
            assert callable(method)


class TestShareRepository:
    def test_share_repository_is_protocol(self) -> None:
        from fb.domain.post.share_repository import ShareRepository

        assert hasattr(ShareRepository, '_is_protocol')
        assert hasattr(ShareRepository, '_is_runtime_protocol')

    def test_share_repository_has_required_methods(self) -> None:
        from fb.domain.post.share_repository import ShareRepository

        required_methods = [
            'save',
            'find_by_id',
            'delete',
            'find_by_post',
            'count_by_post',
        ]

        for method_name in required_methods:
            assert hasattr(ShareRepository, method_name)
            method = getattr(ShareRepository, method_name)
            assert callable(method)
