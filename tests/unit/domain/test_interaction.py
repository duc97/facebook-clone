from __future__ import annotations

import pytest
from datetime import datetime

from fb.domain.shared.entity_id import EntityId
from fb.domain.post.comment import Comment
from fb.domain.post.like import Like
from fb.domain.post.interaction_exceptions import (
    InteractionError,
    CommentNotFoundError,
    AlreadyLikedError,
    NotLikedError,
    CommentPermissionError,
)


class TestComment:
    def test_create_comment_with_valid_data(self) -> None:
        post_id = EntityId.generate()
        author_id = EntityId.generate()
        content = "This is a test comment"

        comment = Comment.create(post_id=post_id, author_id=author_id, content=content)

        assert comment.post_id == post_id
        assert comment.author_id == author_id
        assert comment.content == content
        assert comment.id is not None
        assert comment.created_at is None  # Will be set by infrastructure

    def test_create_comment_with_empty_content_raises_error(self) -> None:
        post_id = EntityId.generate()
        author_id = EntityId.generate()

        with pytest.raises(ValueError, match="Comment content cannot be empty"):
            Comment.create(post_id=post_id, author_id=author_id, content="")

        with pytest.raises(ValueError, match="Comment content cannot be empty"):
            Comment.create(post_id=post_id, author_id=author_id, content="   ")

    def test_create_comment_with_content_too_long_raises_error(self) -> None:
        post_id = EntityId.generate()
        author_id = EntityId.generate()
        content = "x" * 2001

        with pytest.raises(ValueError, match="Comment content exceeds 2000 characters"):
            Comment.create(post_id=post_id, author_id=author_id, content=content)

    def test_create_comment_with_max_length_content_succeeds(self) -> None:
        post_id = EntityId.generate()
        author_id = EntityId.generate()
        content = "x" * 2000

        comment = Comment.create(post_id=post_id, author_id=author_id, content=content)

        assert comment.content == content
        assert len(comment.content) == 2000

    def test_update_content(self) -> None:
        post_id = EntityId.generate()
        author_id = EntityId.generate()
        original_content = "Original content"
        new_content = "Updated content"

        comment = Comment.create(post_id=post_id, author_id=author_id, content=original_content)
        updated_comment = comment.update_content(new_content)

        assert comment.content == original_content  # Original unchanged
        assert updated_comment.content == new_content
        assert updated_comment.id == comment.id
        assert updated_comment.post_id == comment.post_id
        assert updated_comment.author_id == comment.author_id

    def test_comment_is_frozen(self) -> None:
        post_id = EntityId.generate()
        author_id = EntityId.generate()
        content = "Test content"

        comment = Comment.create(post_id=post_id, author_id=author_id, content=content)

        # Should not be able to directly modify attributes
        with pytest.raises(AttributeError):
            comment.content = "New content"  # type: ignore


class TestLike:
    def test_create_like_with_valid_data(self) -> None:
        post_id = EntityId.generate()
        user_id = EntityId.generate()

        like = Like.create(post_id=post_id, user_id=user_id)

        assert like.post_id == post_id
        assert like.user_id == user_id
        assert like.id is not None
        assert like.created_at is None  # Will be set by infrastructure

    def test_like_is_frozen(self) -> None:
        post_id = EntityId.generate()
        user_id = EntityId.generate()

        like = Like.create(post_id=post_id, user_id=user_id)

        # Should not be able to directly modify attributes
        with pytest.raises(AttributeError):
            like.post_id = EntityId.generate()  # type: ignore


class TestInteractionExceptions:
    def test_interaction_error_base_class(self) -> None:
        error = InteractionError("Base interaction error")
        assert error.message == "Base interaction error"
        assert str(error) == "Base interaction error"

    def test_interaction_error_default_message(self) -> None:
        error = InteractionError()
        assert error.message == "Interaction error"

    def test_comment_not_found_error(self) -> None:
        error = CommentNotFoundError("Comment not found")
        assert isinstance(error, InteractionError)
        assert error.message == "Comment not found"

    def test_already_liked_error(self) -> None:
        error = AlreadyLikedError("Already liked")
        assert isinstance(error, InteractionError)
        assert error.message == "Already liked"

    def test_not_liked_error(self) -> None:
        error = NotLikedError("Not liked")
        assert isinstance(error, InteractionError)
        assert error.message == "Not liked"

    def test_comment_permission_error(self) -> None:
        error = CommentPermissionError("Permission denied")
        assert isinstance(error, InteractionError)
        assert error.message == "Permission denied"


class TestCommentRepository:
    def test_comment_repository_is_protocol(self) -> None:
        """Test that CommentRepository is properly defined as a Protocol"""
        from fb.domain.post.comment_repository import CommentRepository
        from typing import runtime_checkable

        # Should be marked as runtime_checkable
        assert hasattr(CommentRepository, '_is_protocol')
        assert hasattr(CommentRepository, '_is_runtime_protocol')

    def test_comment_repository_has_required_methods(self) -> None:
        """Test that CommentRepository has all required methods"""
        from fb.domain.post.comment_repository import CommentRepository
        import inspect

        required_methods = [
            'find_by_id',
            'save',
            'delete',
            'find_by_post',
            'count_by_post'
        ]

        for method_name in required_methods:
            assert hasattr(CommentRepository, method_name)
            method = getattr(CommentRepository, method_name)
            assert callable(method)


class TestLikeRepository:
    def test_like_repository_is_protocol(self) -> None:
        """Test that LikeRepository is properly defined as a Protocol"""
        from fb.domain.post.like_repository import LikeRepository
        from typing import runtime_checkable

        # Should be marked as runtime_checkable
        assert hasattr(LikeRepository, '_is_protocol')
        assert hasattr(LikeRepository, '_is_runtime_protocol')

    def test_like_repository_has_required_methods(self) -> None:
        """Test that LikeRepository has all required methods"""
        from fb.domain.post.like_repository import LikeRepository
        import inspect

        required_methods = [
            'find_by_post_and_user',
            'save',
            'delete',
            'count_by_post',
            'find_by_post'
        ]

        for method_name in required_methods:
            assert hasattr(LikeRepository, method_name)
            method = getattr(LikeRepository, method_name)
            assert callable(method)