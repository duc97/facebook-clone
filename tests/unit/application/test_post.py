from __future__ import annotations

import pytest
from fb.domain.shared.entity_id import EntityId
from fb.domain.post.entities import Post
from fb.domain.post.exceptions import PostNotFoundError, PostPermissionError
from fb.application.post.dtos import (
    CreatePostInput,
    UpdatePostInput,
    DeletePostInput,
    PostOutput,
    GetPostInput,
    GetPostsByAuthorInput,
)
from fb.application.post.create_post import CreatePostUseCase
from fb.application.post.update_post import UpdatePostUseCase
from fb.application.post.delete_post import DeletePostUseCase
from fb.application.post.get_post import GetPostUseCase


class FakePostRepo:
    def __init__(self) -> None:
        self._posts: dict[str, Post] = {}
        self._next_save_will_fail = False

    async def find_by_id(self, post_id: EntityId) -> Post | None:
        return self._posts.get(str(post_id))

    async def save(self, post: Post) -> Post:
        if self._next_save_will_fail:
            self._next_save_will_fail = False
            raise Exception("Database error")
        self._posts[str(post.id)] = post
        return post

    async def update(self, post: Post) -> Post:
        self._posts[str(post.id)] = post
        return post

    async def delete(self, post_id: EntityId) -> None:
        if str(post_id) in self._posts:
            del self._posts[str(post_id)]

    async def find_by_author(self, author_id: EntityId, limit: int = 20, offset: int = 0) -> list[Post]:
        author_posts = [post for post in self._posts.values() if post.author_id == author_id]
        return author_posts[offset:offset + limit]

    async def count_by_author(self, author_id: EntityId) -> int:
        return len([post for post in self._posts.values() if post.author_id == author_id])

    def set_next_save_will_fail(self) -> None:
        self._next_save_will_fail = True


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> FakeUnitOfWork:
        return self

    async def __aexit__(self, *args) -> None:
        pass

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class TestCreatePostUseCase:
    async def test_create_post_successfully(self) -> None:
        repo = FakePostRepo()
        uow = FakeUnitOfWork()
        use_case = CreatePostUseCase(repo, uow)
        author_id = str(EntityId.generate())
        input_data = CreatePostInput(
            author_id=author_id,
            content="Hello world!",
            media_urls=["https://example.com/image.jpg"],
        )

        result = await use_case.execute(input_data)

        assert isinstance(result, PostOutput)
        assert result.author_id == author_id
        assert result.content == "Hello world!"
        assert result.media_urls == ["https://example.com/image.jpg"]
        assert result.like_count == 0
        assert result.comment_count == 0
        assert result.is_published is True
        assert uow.committed is True

    async def test_create_post_without_media_urls(self) -> None:
        repo = FakePostRepo()
        uow = FakeUnitOfWork()
        use_case = CreatePostUseCase(repo, uow)
        author_id = str(EntityId.generate())
        input_data = CreatePostInput(author_id=author_id, content="Hello world!")

        result = await use_case.execute(input_data)

        assert result.media_urls == []

    async def test_create_post_with_empty_content_fails(self) -> None:
        repo = FakePostRepo()
        uow = FakeUnitOfWork()
        use_case = CreatePostUseCase(repo, uow)
        author_id = str(EntityId.generate())
        input_data = CreatePostInput(author_id=author_id, content="")

        with pytest.raises(ValueError, match="Post content cannot be empty"):
            await use_case.execute(input_data)

    async def test_create_post_rolls_back_on_error(self) -> None:
        repo = FakePostRepo()
        repo.set_next_save_will_fail()
        uow = FakeUnitOfWork()
        use_case = CreatePostUseCase(repo, uow)
        author_id = str(EntityId.generate())
        input_data = CreatePostInput(author_id=author_id, content="Hello world!")

        with pytest.raises(Exception, match="Database error"):
            await use_case.execute(input_data)

        assert uow.rolled_back is True


class TestUpdatePostUseCase:
    async def test_update_post_successfully(self) -> None:
        repo = FakePostRepo()
        uow = FakeUnitOfWork()
        use_case = UpdatePostUseCase(repo, uow)

        # Create a post first
        author_id = EntityId.generate()
        post = Post.create(author_id=author_id, content="Original content")
        await repo.save(post)

        input_data = UpdatePostInput(
            post_id=str(post.id),
            user_id=str(author_id),
            content="Updated content",
        )

        result = await use_case.execute(input_data)

        assert result.content == "Updated content"
        assert uow.committed is True

    async def test_update_post_not_found(self) -> None:
        repo = FakePostRepo()
        uow = FakeUnitOfWork()
        use_case = UpdatePostUseCase(repo, uow)

        input_data = UpdatePostInput(
            post_id=str(EntityId.generate()),
            user_id=str(EntityId.generate()),
            content="Updated content",
        )

        with pytest.raises(PostNotFoundError):
            await use_case.execute(input_data)

    async def test_update_post_permission_denied(self) -> None:
        repo = FakePostRepo()
        uow = FakeUnitOfWork()
        use_case = UpdatePostUseCase(repo, uow)

        # Create a post
        author_id = EntityId.generate()
        different_user_id = EntityId.generate()
        post = Post.create(author_id=author_id, content="Original content")
        await repo.save(post)

        input_data = UpdatePostInput(
            post_id=str(post.id),
            user_id=str(different_user_id),
            content="Updated content",
        )

        with pytest.raises(PostPermissionError):
            await use_case.execute(input_data)


class TestDeletePostUseCase:
    async def test_delete_post_successfully(self) -> None:
        repo = FakePostRepo()
        uow = FakeUnitOfWork()
        use_case = DeletePostUseCase(repo, uow)

        # Create a post first
        author_id = EntityId.generate()
        post = Post.create(author_id=author_id, content="To be deleted")
        await repo.save(post)

        input_data = DeletePostInput(
            post_id=str(post.id),
            user_id=str(author_id),
        )

        await use_case.execute(input_data)

        # Verify post is soft deleted (marked as unpublished)
        saved_post = await repo.find_by_id(post.id)
        assert saved_post is not None
        assert saved_post.is_published is False
        assert uow.committed is True

    async def test_delete_post_not_found(self) -> None:
        repo = FakePostRepo()
        uow = FakeUnitOfWork()
        use_case = DeletePostUseCase(repo, uow)

        input_data = DeletePostInput(
            post_id=str(EntityId.generate()),
            user_id=str(EntityId.generate()),
        )

        with pytest.raises(PostNotFoundError):
            await use_case.execute(input_data)

    async def test_delete_post_permission_denied(self) -> None:
        repo = FakePostRepo()
        uow = FakeUnitOfWork()
        use_case = DeletePostUseCase(repo, uow)

        # Create a post
        author_id = EntityId.generate()
        different_user_id = EntityId.generate()
        post = Post.create(author_id=author_id, content="To be deleted")
        await repo.save(post)

        input_data = DeletePostInput(
            post_id=str(post.id),
            user_id=str(different_user_id),
        )

        with pytest.raises(PostPermissionError):
            await use_case.execute(input_data)


class TestGetPostUseCase:
    async def test_get_post_by_id_successfully(self) -> None:
        repo = FakePostRepo()
        use_case = GetPostUseCase(repo)

        # Create a post
        author_id = EntityId.generate()
        post = Post.create(author_id=author_id, content="Test content")
        await repo.save(post)

        input_data = GetPostInput(post_id=str(post.id))

        result = await use_case.execute(input_data)

        assert result.id == str(post.id)
        assert result.content == "Test content"

    async def test_get_post_by_id_not_found(self) -> None:
        repo = FakePostRepo()
        use_case = GetPostUseCase(repo)

        input_data = GetPostInput(post_id=str(EntityId.generate()))

        with pytest.raises(PostNotFoundError):
            await use_case.execute(input_data)

    async def test_get_posts_by_author(self) -> None:
        repo = FakePostRepo()
        use_case = GetPostUseCase(repo)

        # Create multiple posts
        author_id = EntityId.generate()
        other_author_id = EntityId.generate()

        post1 = Post.create(author_id=author_id, content="Post 1")
        post2 = Post.create(author_id=author_id, content="Post 2")
        post3 = Post.create(author_id=other_author_id, content="Other author's post")

        await repo.save(post1)
        await repo.save(post2)
        await repo.save(post3)

        input_data = GetPostsByAuthorInput(author_id=str(author_id))

        result = await use_case.execute_by_author(input_data)

        assert len(result) == 2
        post_contents = [post.content for post in result]
        assert "Post 1" in post_contents
        assert "Post 2" in post_contents
        assert "Other author's post" not in post_contents

    async def test_get_posts_by_author_with_pagination(self) -> None:
        repo = FakePostRepo()
        use_case = GetPostUseCase(repo)

        # Create multiple posts
        author_id = EntityId.generate()

        for i in range(5):
            post = Post.create(author_id=author_id, content=f"Post {i}")
            await repo.save(post)

        input_data = GetPostsByAuthorInput(author_id=str(author_id), limit=2, offset=1)

        result = await use_case.execute_by_author(input_data)

        assert len(result) == 2