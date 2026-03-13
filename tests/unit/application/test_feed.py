from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from fb.application.post.feed_dtos import FeedOutput, GetFeedInput
from fb.application.post.get_feed import GetFeedUseCase
from fb.domain.post.entities import Post
from fb.domain.shared.entity_id import EntityId


# ── Fixed UUID generators for stable test IDs ──

def _uuid(n: int) -> str:
    """Generate a deterministic UUID from an integer for test reproducibility."""
    return str(uuid.UUID(int=n))


USER_1 = _uuid(1)
USER_2 = _uuid(2)
FRIEND_1 = _uuid(10)


class FakeFeedRepo:
    """Fake implementation of FeedRepository for testing."""

    def __init__(self, posts: list[Post] | None = None) -> None:
        self._posts = {str(p.id): p for p in (posts or [])}

    async def get_feed_post_ids(
        self, user_id: EntityId, friend_ids: list[EntityId], limit: int = 20, offset: int = 0
    ) -> list[EntityId]:
        matching = [
            p for p in self._posts.values()
            if p.author_id == user_id or p.author_id in friend_ids
        ]
        matching.sort(key=lambda p: p.created_at or datetime.min, reverse=True)
        return [p.id for p in matching[offset:offset + limit]]

    async def get_feed_posts(self, post_ids: list[EntityId]) -> list[Post]:
        return [self._posts[str(pid)] for pid in post_ids if str(pid) in self._posts]

    async def get_feed_total_count(
        self, user_id: EntityId, friend_ids: list[EntityId]
    ) -> int:
        return sum(
            1 for p in self._posts.values()
            if p.author_id == user_id or p.author_id in friend_ids
        )


class FakeFriendRepo:
    """Fake implementation of FriendRepository for testing."""

    def __init__(self, friends: dict[str, list[EntityId]] | None = None) -> None:
        self._friends = friends or {}

    async def get_friends(
        self, user_id: EntityId, limit: int = 20, offset: int = 0
    ) -> list[EntityId]:
        return self._friends.get(str(user_id), [])


class FakeFeedCache:
    """Fake implementation of FeedCacheService for testing."""

    def __init__(self) -> None:
        self._cache: dict[str, list[str]] = {}

    async def get_feed(self, user_id: str) -> list[str] | None:
        return self._cache.get(user_id)

    async def set_feed(
        self, user_id: str, post_ids: list[str], ttl: int | None = None
    ) -> None:
        self._cache[user_id] = post_ids

    async def invalidate(self, user_id: str) -> None:
        self._cache.pop(user_id, None)


_SENTINEL = object()


def create_post(
    author_id: str,
    content: str = "Test content",
    created_at: datetime | None | object = _SENTINEL,
    like_count: int = 0,
    comment_count: int = 0,
    post_id: EntityId | None = None,
) -> Post:
    """Helper to create test posts with valid UUIDs.

    Pass created_at=None explicitly to create a post with no timestamp.
    """
    ts = datetime.now() if created_at is _SENTINEL else created_at
    return Post(
        id=post_id or EntityId.generate(),
        author_id=EntityId.from_str(author_id),
        content=content,
        media_urls=(),
        like_count=like_count,
        comment_count=comment_count,
        is_published=True,
        created_at=ts,  # type: ignore[arg-type]
    )


class TestGetFeedUseCase:
    """Test GetFeedUseCase functionality."""

    def test_init_creates_use_case_with_required_dependencies(self) -> None:
        """Should create use case with required dependencies."""
        feed_repo = FakeFeedRepo()
        friend_repo = FakeFriendRepo()

        use_case = GetFeedUseCase(feed_repo=feed_repo, friend_repo=friend_repo)

        assert use_case._feed_repo is feed_repo
        assert use_case._friend_repo is friend_repo
        assert use_case._feed_cache is None

    def test_init_creates_use_case_with_optional_cache(self) -> None:
        """Should create use case with optional cache service."""
        feed_repo = FakeFeedRepo()
        friend_repo = FakeFriendRepo()
        feed_cache = FakeFeedCache()

        use_case = GetFeedUseCase(
            feed_repo=feed_repo, friend_repo=friend_repo, feed_cache=feed_cache
        )

        assert use_case._feed_cache is feed_cache

    @pytest.mark.asyncio
    async def test_execute_returns_empty_feed_for_user_with_no_posts_or_friends(self) -> None:
        """Should return empty feed when user has no posts and no friends."""
        feed_repo = FakeFeedRepo([])
        friend_repo = FakeFriendRepo({})
        use_case = GetFeedUseCase(feed_repo=feed_repo, friend_repo=friend_repo)

        input_data = GetFeedInput(user_id=USER_1)
        result = await use_case.execute(input_data)

        assert isinstance(result, FeedOutput)
        assert result.posts == []
        assert result.total_count == 0
        assert result.has_next_page is False

    @pytest.mark.asyncio
    async def test_execute_returns_user_own_posts(self) -> None:
        """Should return user's own posts in feed."""
        post = create_post(USER_1, "My post")
        feed_repo = FakeFeedRepo([post])
        friend_repo = FakeFriendRepo({})
        use_case = GetFeedUseCase(feed_repo=feed_repo, friend_repo=friend_repo)

        input_data = GetFeedInput(user_id=USER_1)
        result = await use_case.execute(input_data)

        assert len(result.posts) == 1
        assert result.posts[0].id == str(post.id)
        assert result.posts[0].author_id == USER_1
        assert result.posts[0].content == "My post"
        assert result.total_count == 1
        assert result.has_next_page is False

    @pytest.mark.asyncio
    async def test_execute_returns_friends_posts(self) -> None:
        """Should return friends' posts in feed."""
        post = create_post(FRIEND_1, "Friend's post")
        feed_repo = FakeFeedRepo([post])
        friend_repo = FakeFriendRepo({USER_1: [EntityId.from_str(FRIEND_1)]})
        use_case = GetFeedUseCase(feed_repo=feed_repo, friend_repo=friend_repo)

        input_data = GetFeedInput(user_id=USER_1)
        result = await use_case.execute(input_data)

        assert len(result.posts) == 1
        assert result.posts[0].id == str(post.id)
        assert result.posts[0].author_id == FRIEND_1
        assert result.posts[0].content == "Friend's post"

    @pytest.mark.asyncio
    async def test_execute_returns_mixed_user_and_friends_posts(self) -> None:
        """Should return both user's and friends' posts in feed."""
        user_post = create_post(USER_1, "My post")
        friend_post = create_post(FRIEND_1, "Friend's post")

        feed_repo = FakeFeedRepo([user_post, friend_post])
        friend_repo = FakeFriendRepo({USER_1: [EntityId.from_str(FRIEND_1)]})
        use_case = GetFeedUseCase(feed_repo=feed_repo, friend_repo=friend_repo)

        input_data = GetFeedInput(user_id=USER_1)
        result = await use_case.execute(input_data)

        assert len(result.posts) == 2
        assert result.total_count == 2
        post_ids = [p.id for p in result.posts]
        assert str(user_post.id) in post_ids
        assert str(friend_post.id) in post_ids

    @pytest.mark.asyncio
    async def test_execute_respects_limit_parameter(self) -> None:
        """Should respect limit parameter for pagination."""
        posts = [
            create_post(USER_1, f"Post {i}")
            for i in range(5)
        ]

        feed_repo = FakeFeedRepo(posts)
        friend_repo = FakeFriendRepo({})
        use_case = GetFeedUseCase(feed_repo=feed_repo, friend_repo=friend_repo)

        input_data = GetFeedInput(user_id=USER_1, limit=3)
        result = await use_case.execute(input_data)

        assert len(result.posts) == 3
        assert result.total_count == 5
        assert result.has_next_page is True

    @pytest.mark.asyncio
    async def test_execute_respects_offset_parameter(self) -> None:
        """Should respect offset parameter for pagination."""
        posts = [
            create_post(USER_1, f"Post {i}")
            for i in range(5)
        ]

        feed_repo = FakeFeedRepo(posts)
        friend_repo = FakeFriendRepo({})
        use_case = GetFeedUseCase(feed_repo=feed_repo, friend_repo=friend_repo)

        input_data = GetFeedInput(user_id=USER_1, limit=2, offset=3)
        result = await use_case.execute(input_data)

        assert len(result.posts) == 2
        assert result.total_count == 5
        assert result.has_next_page is False

    @pytest.mark.asyncio
    async def test_execute_caps_limit_to_maximum_value(self) -> None:
        """Should cap limit to maximum of 50."""
        feed_repo = FakeFeedRepo([])
        friend_repo = FakeFriendRepo({})
        use_case = GetFeedUseCase(feed_repo=feed_repo, friend_repo=friend_repo)

        # Mock the feed_repo to track the limit used
        feed_repo.get_feed_post_ids = AsyncMock(return_value=[])

        input_data = GetFeedInput(user_id=USER_1, limit=100)
        await use_case.execute(input_data)

        feed_repo.get_feed_post_ids.assert_called_once()
        call_args = feed_repo.get_feed_post_ids.call_args[1]
        assert call_args["limit"] == 50

    @pytest.mark.asyncio
    async def test_execute_enforces_minimum_limit_of_one(self) -> None:
        """Should enforce minimum limit of 1."""
        feed_repo = FakeFeedRepo([])
        friend_repo = FakeFriendRepo({})
        use_case = GetFeedUseCase(feed_repo=feed_repo, friend_repo=friend_repo)

        # Mock the feed_repo to track the limit used
        feed_repo.get_feed_post_ids = AsyncMock(return_value=[])

        input_data = GetFeedInput(user_id=USER_1, limit=0)
        await use_case.execute(input_data)

        feed_repo.get_feed_post_ids.assert_called_once()
        call_args = feed_repo.get_feed_post_ids.call_args[1]
        assert call_args["limit"] == 1

    @pytest.mark.asyncio
    async def test_execute_enforces_minimum_offset_of_zero(self) -> None:
        """Should enforce minimum offset of 0."""
        feed_repo = FakeFeedRepo([])
        friend_repo = FakeFriendRepo({})
        use_case = GetFeedUseCase(feed_repo=feed_repo, friend_repo=friend_repo)

        # Mock the feed_repo to track the offset used
        feed_repo.get_feed_post_ids = AsyncMock(return_value=[])

        input_data = GetFeedInput(user_id=USER_1, offset=-5)
        await use_case.execute(input_data)

        feed_repo.get_feed_post_ids.assert_called_once()
        call_args = feed_repo.get_feed_post_ids.call_args[1]
        assert call_args["offset"] == 0

    @pytest.mark.asyncio
    async def test_execute_converts_post_to_output_dto_correctly(self) -> None:
        """Should convert Post entity to FeedPostOutput DTO correctly."""
        created_at = datetime(2024, 1, 1, 12, 0, 0)
        post = Post(
            id=EntityId.generate(),
            author_id=EntityId.from_str(USER_1),
            content="Test content",
            media_urls=("https://example.com/image.jpg",),
            like_count=42,
            comment_count=7,
            is_published=True,
            created_at=created_at,
        )

        feed_repo = FakeFeedRepo([post])
        friend_repo = FakeFriendRepo({})
        use_case = GetFeedUseCase(feed_repo=feed_repo, friend_repo=friend_repo)

        input_data = GetFeedInput(user_id=USER_1)
        result = await use_case.execute(input_data)

        output_post = result.posts[0]
        assert output_post.id == str(post.id)
        assert output_post.author_id == str(post.author_id)
        assert output_post.content == "Test content"
        assert output_post.media_urls == ["https://example.com/image.jpg"]
        assert output_post.like_count == 42
        assert output_post.comment_count == 7
        assert output_post.created_at == str(created_at)

    @pytest.mark.asyncio
    async def test_execute_handles_post_with_none_created_at(self) -> None:
        """Should handle posts with None created_at gracefully."""
        post = create_post(USER_1, created_at=None)

        feed_repo = FakeFeedRepo([post])
        friend_repo = FakeFriendRepo({})
        use_case = GetFeedUseCase(feed_repo=feed_repo, friend_repo=friend_repo)

        input_data = GetFeedInput(user_id=USER_1)
        result = await use_case.execute(input_data)

        assert result.posts[0].created_at is None
