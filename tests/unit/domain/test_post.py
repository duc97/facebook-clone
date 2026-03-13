from __future__ import annotations

import pytest
from datetime import datetime
from fb.domain.shared.entity_id import EntityId
from fb.domain.post.entities import Post
from fb.domain.post.value_objects import PostContent
from fb.domain.post.exceptions import (
    PostError,
    PostNotFoundError,
    PostContentTooLongError,
    PostPermissionError,
)


class TestPostEntity:
    def test_create_post_with_minimal_data(self) -> None:
        author_id = EntityId.generate()
        content = "Hello world!"

        post = Post.create(author_id=author_id, content=content)

        assert post.id is not None
        assert post.author_id == author_id
        assert post.content == content
        assert post.media_urls == ()
        assert post.like_count == 0
        assert post.comment_count == 0
        assert post.is_published is True
        assert post.created_at is None
        assert post.updated_at is None

    def test_create_post_with_media_urls(self) -> None:
        author_id = EntityId.generate()
        content = "Check out my photos!"
        media_urls = ("https://example.com/img1.jpg", "https://example.com/img2.jpg")

        post = Post.create(author_id=author_id, content=content, media_urls=media_urls)

        assert post.media_urls == media_urls

    def test_post_is_frozen(self) -> None:
        author_id = EntityId.generate()
        post = Post.create(author_id=author_id, content="Test")

        with pytest.raises(Exception):  # FrozenInstanceError or similar
            post.content = "Changed"  # type: ignore

    def test_update_content(self) -> None:
        author_id = EntityId.generate()
        original_post = Post.create(author_id=author_id, content="Original content")
        new_content = "Updated content"

        updated_post = original_post.update_content(new_content)

        assert updated_post.content == new_content
        assert updated_post.id == original_post.id
        assert updated_post.author_id == original_post.author_id
        assert original_post.content == "Original content"  # Original unchanged

    def test_increment_like_count(self) -> None:
        author_id = EntityId.generate()
        post = Post.create(author_id=author_id, content="Test")

        liked_post = post.increment_like_count()

        assert liked_post.like_count == 1
        assert post.like_count == 0  # Original unchanged

    def test_decrement_like_count(self) -> None:
        author_id = EntityId.generate()
        post = Post.create(author_id=author_id, content="Test")
        liked_post = post.increment_like_count().increment_like_count()

        unliked_post = liked_post.decrement_like_count()

        assert unliked_post.like_count == 1
        assert liked_post.like_count == 2  # Original unchanged

    def test_decrement_like_count_cannot_go_negative(self) -> None:
        author_id = EntityId.generate()
        post = Post.create(author_id=author_id, content="Test")

        unliked_post = post.decrement_like_count()

        assert unliked_post.like_count == 0

    def test_increment_comment_count(self) -> None:
        author_id = EntityId.generate()
        post = Post.create(author_id=author_id, content="Test")

        commented_post = post.increment_comment_count()

        assert commented_post.comment_count == 1
        assert post.comment_count == 0  # Original unchanged

    def test_decrement_comment_count(self) -> None:
        author_id = EntityId.generate()
        post = Post.create(author_id=author_id, content="Test")
        commented_post = post.increment_comment_count().increment_comment_count()

        decremented_post = commented_post.decrement_comment_count()

        assert decremented_post.comment_count == 1
        assert commented_post.comment_count == 2  # Original unchanged

    def test_decrement_comment_count_cannot_go_negative(self) -> None:
        author_id = EntityId.generate()
        post = Post.create(author_id=author_id, content="Test")

        decremented_post = post.decrement_comment_count()

        assert decremented_post.comment_count == 0

    def test_delete_post(self) -> None:
        author_id = EntityId.generate()
        post = Post.create(author_id=author_id, content="Test")

        deleted_post = post.delete()

        assert deleted_post.is_published is False
        assert post.is_published is True  # Original unchanged

    def test_post_with_timestamps(self) -> None:
        author_id = EntityId.generate()
        created_at = datetime.now()
        updated_at = datetime.now()

        post = Post(
            id=EntityId.generate(),
            author_id=author_id,
            content="Test",
            media_urls=(),
            created_at=created_at,
            updated_at=updated_at,
        )

        assert post.created_at == created_at
        assert post.updated_at == updated_at


class TestPostContent:
    def test_valid_content(self) -> None:
        content = "This is valid content"

        post_content = PostContent(value=content)

        assert post_content.value == content

    def test_empty_content_raises_error(self) -> None:
        with pytest.raises(ValueError, match="Post content cannot be empty"):
            PostContent(value="")

    def test_whitespace_only_content_raises_error(self) -> None:
        with pytest.raises(ValueError, match="Post content cannot be empty"):
            PostContent(value="   ")

    def test_content_too_long_raises_error(self) -> None:
        long_content = "x" * 5001

        with pytest.raises(ValueError, match="Post content exceeds 5000 characters"):
            PostContent(value=long_content)

    def test_content_at_max_length_is_valid(self) -> None:
        max_length_content = "x" * 5000

        post_content = PostContent(value=max_length_content)

        assert post_content.value == max_length_content

    def test_post_content_is_frozen(self) -> None:
        post_content = PostContent(value="Test")

        with pytest.raises(Exception):  # FrozenInstanceError or similar
            post_content.value = "Changed"  # type: ignore


class TestPostExceptions:
    def test_post_error_with_default_message(self) -> None:
        error = PostError()
        assert error.message == "Post error"
        assert str(error) == "Post error"

    def test_post_error_with_custom_message(self) -> None:
        custom_message = "Custom error message"
        error = PostError(custom_message)
        assert error.message == custom_message
        assert str(error) == custom_message

    def test_post_not_found_error_inherits_from_post_error(self) -> None:
        error = PostNotFoundError("Post not found")
        assert isinstance(error, PostError)
        assert error.message == "Post not found"

    def test_post_content_too_long_error_inherits_from_post_error(self) -> None:
        error = PostContentTooLongError("Content too long")
        assert isinstance(error, PostError)
        assert error.message == "Content too long"

    def test_post_permission_error_inherits_from_post_error(self) -> None:
        error = PostPermissionError("Permission denied")
        assert isinstance(error, PostError)
        assert error.message == "Permission denied"