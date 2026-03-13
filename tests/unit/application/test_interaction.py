from __future__ import annotations

import pytest
from dataclasses import dataclass
from datetime import datetime

from fb.domain.shared.entity_id import EntityId
from fb.domain.post.comment import Comment
from fb.domain.post.like import Like
from fb.domain.post.entities import Post
from fb.domain.post.exceptions import PostNotFoundError
from fb.domain.post.interaction_exceptions import (
    CommentNotFoundError,
    AlreadyLikedError,
    NotLikedError,
    CommentPermissionError,
)
from fb.application.shared.interfaces import UnitOfWork
from fb.application.post.interaction_dtos import (
    CreateCommentInput,
    DeleteCommentInput,
    LikePostInput,
    UnlikePostInput,
    CommentOutput,
    LikeOutput,
    CommentsListOutput,
)
from fb.application.post.create_comment import CreateCommentUseCase
from fb.application.post.delete_comment import DeleteCommentUseCase
from fb.application.post.like_post import LikePostUseCase
from fb.application.post.unlike_post import UnlikePostUseCase
from fb.application.post.get_comments import GetCommentsUseCase


# Test Fakes
class FakeCommentRepo:
    def __init__(self) -> None:
        self._comments: dict[str, Comment] = {}

    async def find_by_id(self, comment_id: EntityId) -> Comment | None:
        return self._comments.get(str(comment_id))

    async def save(self, comment: Comment) -> Comment:
        self._comments[str(comment.id)] = comment
        return comment

    async def delete(self, comment_id: EntityId) -> None:
        self._comments.pop(str(comment_id), None)

    async def find_by_post(self, post_id: EntityId, limit: int = 20, offset: int = 0) -> list[Comment]:
        matching = [c for c in self._comments.values() if c.post_id == post_id]
        return matching[offset:offset+limit]

    async def count_by_post(self, post_id: EntityId) -> int:
        return sum(1 for c in self._comments.values() if c.post_id == post_id)


class FakeLikeRepo:
    def __init__(self) -> None:
        self._likes: dict[str, Like] = {}

    async def find_by_post_and_user(self, post_id: EntityId, user_id: EntityId) -> Like | None:
        for like in self._likes.values():
            if like.post_id == post_id and like.user_id == user_id:
                return like
        return None

    async def save(self, like: Like) -> Like:
        self._likes[str(like.id)] = like
        return like

    async def delete(self, like_id: EntityId) -> None:
        self._likes.pop(str(like_id), None)

    async def count_by_post(self, post_id: EntityId) -> int:
        return sum(1 for l in self._likes.values() if l.post_id == post_id)

    async def find_by_post(self, post_id: EntityId, limit: int = 20, offset: int = 0) -> list[Like]:
        matching = [l for l in self._likes.values() if l.post_id == post_id]
        return matching[offset:offset+limit]


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


class TestCreateCommentUseCase:
    async def test_create_comment_successfully(self) -> None:
        # Arrange
        post_id = EntityId.generate()
        author_id = EntityId.generate()
        post = Post.create(author_id=author_id, content="Test post")
        # Use replace to set the id
        from dataclasses import replace
        post = replace(post, id=post_id)

        comment_repo = FakeCommentRepo()
        post_repo = FakePostRepo({str(post_id): post})
        uow = FakeUnitOfWork()

        use_case = CreateCommentUseCase(comment_repo, post_repo, uow)
        input_data = CreateCommentInput(
            post_id=str(post_id),
            author_id=str(author_id),
            content="Great post!"
        )

        # Act
        result = await use_case.execute(input_data)

        # Assert
        assert isinstance(result, CommentOutput)
        assert result.post_id == str(post_id)
        assert result.author_id == str(author_id)
        assert result.content == "Great post!"
        assert result.id is not None
        assert uow.committed

    async def test_create_comment_post_not_found_raises_error(self) -> None:
        # Arrange
        post_id = EntityId.generate()
        author_id = EntityId.generate()

        comment_repo = FakeCommentRepo()
        post_repo = FakePostRepo()
        uow = FakeUnitOfWork()

        use_case = CreateCommentUseCase(comment_repo, post_repo, uow)
        input_data = CreateCommentInput(
            post_id=str(post_id),
            author_id=str(author_id),
            content="Great post!"
        )

        # Act & Assert
        with pytest.raises(PostNotFoundError):
            await use_case.execute(input_data)

        assert not uow.committed

    async def test_create_comment_increments_post_comment_count(self) -> None:
        # Arrange
        post_id = EntityId.generate()
        author_id = EntityId.generate()
        post = Post.create(author_id=author_id, content="Test post")
        # Use replace to set the id
        from dataclasses import replace
        post = replace(post, id=post_id)
        initial_count = post.comment_count

        comment_repo = FakeCommentRepo()
        post_repo = FakePostRepo({str(post_id): post})
        uow = FakeUnitOfWork()

        use_case = CreateCommentUseCase(comment_repo, post_repo, uow)
        input_data = CreateCommentInput(
            post_id=str(post_id),
            author_id=str(author_id),
            content="Great post!"
        )

        # Act
        await use_case.execute(input_data)

        # Assert
        updated_post = await post_repo.find_by_id(post_id)
        assert updated_post is not None
        assert updated_post.comment_count == initial_count + 1


class TestDeleteCommentUseCase:
    async def test_delete_comment_successfully(self) -> None:
        # Arrange
        post_id = EntityId.generate()
        author_id = EntityId.generate()
        comment_id = EntityId.generate()

        post = Post.create(author_id=author_id, content="Test post")
        # Use replace to set the id
        from dataclasses import replace
        post = replace(post, id=post_id).increment_comment_count()

        comment = Comment.create(post_id=post_id, author_id=author_id, content="Test comment")
        comment = Comment(
            id=comment_id,
            post_id=comment.post_id,
            author_id=comment.author_id,
            content=comment.content,
            created_at=comment.created_at,
            updated_at=comment.updated_at
        )

        comment_repo = FakeCommentRepo()
        await comment_repo.save(comment)
        post_repo = FakePostRepo({str(post_id): post})
        uow = FakeUnitOfWork()

        use_case = DeleteCommentUseCase(comment_repo, post_repo, uow)
        input_data = DeleteCommentInput(comment_id=str(comment_id), user_id=str(author_id))

        # Act
        await use_case.execute(input_data)

        # Assert
        deleted_comment = await comment_repo.find_by_id(comment_id)
        assert deleted_comment is None
        assert uow.committed

    async def test_delete_comment_not_found_raises_error(self) -> None:
        # Arrange
        comment_id = EntityId.generate()
        user_id = EntityId.generate()

        comment_repo = FakeCommentRepo()
        post_repo = FakePostRepo()
        uow = FakeUnitOfWork()

        use_case = DeleteCommentUseCase(comment_repo, post_repo, uow)
        input_data = DeleteCommentInput(comment_id=str(comment_id), user_id=str(user_id))

        # Act & Assert
        with pytest.raises(CommentNotFoundError):
            await use_case.execute(input_data)

        assert not uow.committed

    async def test_delete_comment_permission_denied_raises_error(self) -> None:
        # Arrange
        post_id = EntityId.generate()
        author_id = EntityId.generate()
        other_user_id = EntityId.generate()
        comment_id = EntityId.generate()

        comment = Comment.create(post_id=post_id, author_id=author_id, content="Test comment")
        comment = Comment(
            id=comment_id,
            post_id=comment.post_id,
            author_id=comment.author_id,
            content=comment.content,
            created_at=comment.created_at,
            updated_at=comment.updated_at
        )

        comment_repo = FakeCommentRepo()
        await comment_repo.save(comment)
        post_repo = FakePostRepo()
        uow = FakeUnitOfWork()

        use_case = DeleteCommentUseCase(comment_repo, post_repo, uow)
        input_data = DeleteCommentInput(comment_id=str(comment_id), user_id=str(other_user_id))

        # Act & Assert
        with pytest.raises(CommentPermissionError):
            await use_case.execute(input_data)

        assert not uow.committed

    async def test_delete_comment_decrements_post_comment_count(self) -> None:
        # Arrange
        post_id = EntityId.generate()
        author_id = EntityId.generate()
        comment_id = EntityId.generate()

        post = Post.create(author_id=author_id, content="Test post")
        # Use replace to set the id
        from dataclasses import replace
        post = replace(post, id=post_id).increment_comment_count()
        initial_count = post.comment_count

        comment = Comment.create(post_id=post_id, author_id=author_id, content="Test comment")
        comment = Comment(
            id=comment_id,
            post_id=comment.post_id,
            author_id=comment.author_id,
            content=comment.content,
            created_at=comment.created_at,
            updated_at=comment.updated_at
        )

        comment_repo = FakeCommentRepo()
        await comment_repo.save(comment)
        post_repo = FakePostRepo({str(post_id): post})
        uow = FakeUnitOfWork()

        use_case = DeleteCommentUseCase(comment_repo, post_repo, uow)
        input_data = DeleteCommentInput(comment_id=str(comment_id), user_id=str(author_id))

        # Act
        await use_case.execute(input_data)

        # Assert
        updated_post = await post_repo.find_by_id(post_id)
        assert updated_post is not None
        assert updated_post.comment_count == initial_count - 1


class TestLikePostUseCase:
    async def test_like_post_successfully(self) -> None:
        # Arrange
        post_id = EntityId.generate()
        user_id = EntityId.generate()
        author_id = EntityId.generate()

        post = Post.create(author_id=author_id, content="Test post")
        # Use replace to set the id
        from dataclasses import replace
        post = replace(post, id=post_id)

        like_repo = FakeLikeRepo()
        post_repo = FakePostRepo({str(post_id): post})
        uow = FakeUnitOfWork()

        use_case = LikePostUseCase(like_repo, post_repo, uow)
        input_data = LikePostInput(post_id=str(post_id), user_id=str(user_id))

        # Act
        result = await use_case.execute(input_data)

        # Assert
        assert isinstance(result, LikeOutput)
        assert result.post_id == str(post_id)
        assert result.user_id == str(user_id)
        assert result.id is not None
        assert uow.committed

    async def test_like_post_not_found_raises_error(self) -> None:
        # Arrange
        post_id = EntityId.generate()
        user_id = EntityId.generate()

        like_repo = FakeLikeRepo()
        post_repo = FakePostRepo()
        uow = FakeUnitOfWork()

        use_case = LikePostUseCase(like_repo, post_repo, uow)
        input_data = LikePostInput(post_id=str(post_id), user_id=str(user_id))

        # Act & Assert
        with pytest.raises(PostNotFoundError):
            await use_case.execute(input_data)

        assert not uow.committed

    async def test_like_post_already_liked_raises_error(self) -> None:
        # Arrange
        post_id = EntityId.generate()
        user_id = EntityId.generate()
        author_id = EntityId.generate()

        post = Post.create(author_id=author_id, content="Test post")
        # Use replace to set the id
        from dataclasses import replace
        post = replace(post, id=post_id)

        existing_like = Like.create(post_id=post_id, user_id=user_id)

        like_repo = FakeLikeRepo()
        await like_repo.save(existing_like)
        post_repo = FakePostRepo({str(post_id): post})
        uow = FakeUnitOfWork()

        use_case = LikePostUseCase(like_repo, post_repo, uow)
        input_data = LikePostInput(post_id=str(post_id), user_id=str(user_id))

        # Act & Assert
        with pytest.raises(AlreadyLikedError):
            await use_case.execute(input_data)

        assert not uow.committed

    async def test_like_post_increments_post_like_count(self) -> None:
        # Arrange
        post_id = EntityId.generate()
        user_id = EntityId.generate()
        author_id = EntityId.generate()

        post = Post.create(author_id=author_id, content="Test post")
        # Use replace to set the id
        from dataclasses import replace
        post = replace(post, id=post_id)
        initial_count = post.like_count

        like_repo = FakeLikeRepo()
        post_repo = FakePostRepo({str(post_id): post})
        uow = FakeUnitOfWork()

        use_case = LikePostUseCase(like_repo, post_repo, uow)
        input_data = LikePostInput(post_id=str(post_id), user_id=str(user_id))

        # Act
        await use_case.execute(input_data)

        # Assert
        updated_post = await post_repo.find_by_id(post_id)
        assert updated_post is not None
        assert updated_post.like_count == initial_count + 1


class TestUnlikePostUseCase:
    async def test_unlike_post_successfully(self) -> None:
        # Arrange
        post_id = EntityId.generate()
        user_id = EntityId.generate()
        author_id = EntityId.generate()

        post = Post.create(author_id=author_id, content="Test post")
        # Use replace to set the id
        from dataclasses import replace
        post = replace(post, id=post_id).increment_like_count()

        like = Like.create(post_id=post_id, user_id=user_id)

        like_repo = FakeLikeRepo()
        await like_repo.save(like)
        post_repo = FakePostRepo({str(post_id): post})
        uow = FakeUnitOfWork()

        use_case = UnlikePostUseCase(like_repo, post_repo, uow)
        input_data = UnlikePostInput(post_id=str(post_id), user_id=str(user_id))

        # Act
        await use_case.execute(input_data)

        # Assert
        remaining_like = await like_repo.find_by_post_and_user(post_id, user_id)
        assert remaining_like is None
        assert uow.committed

    async def test_unlike_post_not_liked_raises_error(self) -> None:
        # Arrange
        post_id = EntityId.generate()
        user_id = EntityId.generate()

        like_repo = FakeLikeRepo()
        post_repo = FakePostRepo()
        uow = FakeUnitOfWork()

        use_case = UnlikePostUseCase(like_repo, post_repo, uow)
        input_data = UnlikePostInput(post_id=str(post_id), user_id=str(user_id))

        # Act & Assert
        with pytest.raises(NotLikedError):
            await use_case.execute(input_data)

        assert not uow.committed

    async def test_unlike_post_decrements_post_like_count(self) -> None:
        # Arrange
        post_id = EntityId.generate()
        user_id = EntityId.generate()
        author_id = EntityId.generate()

        post = Post.create(author_id=author_id, content="Test post")
        # Use replace to set the id
        from dataclasses import replace
        post = replace(post, id=post_id).increment_like_count()
        initial_count = post.like_count

        like = Like.create(post_id=post_id, user_id=user_id)

        like_repo = FakeLikeRepo()
        await like_repo.save(like)
        post_repo = FakePostRepo({str(post_id): post})
        uow = FakeUnitOfWork()

        use_case = UnlikePostUseCase(like_repo, post_repo, uow)
        input_data = UnlikePostInput(post_id=str(post_id), user_id=str(user_id))

        # Act
        await use_case.execute(input_data)

        # Assert
        updated_post = await post_repo.find_by_id(post_id)
        assert updated_post is not None
        assert updated_post.like_count == initial_count - 1


class TestGetCommentsUseCase:
    async def test_get_comments_successfully(self) -> None:
        # Arrange
        post_id = EntityId.generate()
        author_id = EntityId.generate()

        comment1 = Comment.create(post_id=post_id, author_id=author_id, content="First comment")
        comment2 = Comment.create(post_id=post_id, author_id=author_id, content="Second comment")

        comment_repo = FakeCommentRepo()
        await comment_repo.save(comment1)
        await comment_repo.save(comment2)

        use_case = GetCommentsUseCase(comment_repo)

        # Act
        result = await use_case.execute(str(post_id))

        # Assert
        assert isinstance(result, CommentsListOutput)
        assert len(result.comments) == 2
        assert result.total_count == 2
        assert not result.has_next_page

    async def test_get_comments_with_pagination(self) -> None:
        # Arrange
        post_id = EntityId.generate()
        author_id = EntityId.generate()

        # Create 3 comments
        comment_repo = FakeCommentRepo()
        for i in range(3):
            comment = Comment.create(post_id=post_id, author_id=author_id, content=f"Comment {i}")
            await comment_repo.save(comment)

        use_case = GetCommentsUseCase(comment_repo)

        # Act - Get first 2 comments
        result = await use_case.execute(str(post_id), limit=2, offset=0)

        # Assert
        assert len(result.comments) == 2
        assert result.total_count == 3
        assert result.has_next_page

    async def test_get_comments_empty_result(self) -> None:
        # Arrange
        post_id = EntityId.generate()
        comment_repo = FakeCommentRepo()
        use_case = GetCommentsUseCase(comment_repo)

        # Act
        result = await use_case.execute(str(post_id))

        # Assert
        assert len(result.comments) == 0
        assert result.total_count == 0
        assert not result.has_next_page