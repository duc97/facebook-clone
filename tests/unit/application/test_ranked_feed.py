from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest

from fb.application.post.feed_dtos import FeedOutput, FeedPostOutput, GetRankedFeedInput
from fb.application.post.get_feed import GetFeedUseCase
from fb.domain.post.entities import Post
from fb.domain.shared.entity_id import EntityId


# ── Helpers ──────────────────────────────────────────────────────────────────


def _uuid(n: int) -> str:
    return str(uuid.UUID(int=n))


USER_1 = _uuid(1)
FRIEND_1 = _uuid(10)
FRIEND_2 = _uuid(20)


class FakeFeedRepo:
    """Fake implementation of FeedRepository for testing ranked feed."""

    def __init__(self, posts: list[Post] | None = None) -> None:
        self._posts = {str(p.id): p for p in (posts or [])}
        self.last_limit: int | None = None

    async def get_feed_post_ids(
        self, user_id: EntityId, friend_ids: list[EntityId], limit: int = 20, offset: int = 0
    ) -> list[EntityId]:
        matching = [
            p for p in self._posts.values()
            if p.author_id == user_id or p.author_id in friend_ids
        ]
        matching.sort(key=lambda p: p.created_at or datetime.min, reverse=True)
        self.last_limit = limit
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


class FakeInteractionHistory:
    """Fake interaction history provider for testing."""

    def __init__(
        self,
        interactions: dict[tuple[str, str], tuple[int, int]] | None = None,
    ) -> None:
        self._interactions = interactions or {}

    async def get_interaction_counts(
        self, user_id: EntityId, author_id: EntityId
    ) -> tuple[int, int]:
        key = (str(user_id), str(author_id))
        return self._interactions.get(key, (0, 0))

    async def get_batch_interaction_counts(
        self, user_id: EntityId, author_ids: list[EntityId]
    ) -> dict[str, tuple[int, int]]:
        result: dict[str, tuple[int, int]] = {}
        for aid in author_ids:
            key = (str(user_id), str(aid))
            result[str(aid)] = self._interactions.get(key, (0, 0))
        return result


def _make_post(
    *,
    author_id: str,
    hours_old: float = 1.0,
    like_count: int = 0,
    comment_count: int = 0,
    content: str = "Test content",
    media_urls: tuple[str, ...] = (),
    post_id: int | None = None,
) -> Post:
    created_at = datetime.utcnow() - timedelta(hours=hours_old)
    return Post(
        id=EntityId.from_str(_uuid(post_id or hash(author_id + str(hours_old)) % 10000)),
        author_id=EntityId.from_str(author_id),
        content=content,
        media_urls=media_urls,
        like_count=like_count,
        comment_count=comment_count,
        is_published=True,
        created_at=created_at,
    )


# ── Tests ────────────────────────────────────────────────────────────────────


class TestGetRankedFeedInput:
    """Test the GetRankedFeedInput DTO."""

    def test_defaults(self) -> None:
        """Should have sensible defaults."""
        dto = GetRankedFeedInput(user_id=USER_1)
        assert dto.user_id == USER_1
        assert dto.limit == 20
        assert dto.mode == "ranked"

    def test_chronological_mode(self) -> None:
        """Should accept chronological mode."""
        dto = GetRankedFeedInput(user_id=USER_1, mode="chronological")
        assert dto.mode == "chronological"

    def test_is_frozen(self) -> None:
        """DTO should be immutable."""
        dto = GetRankedFeedInput(user_id=USER_1)
        with pytest.raises(AttributeError):
            dto.limit = 10  # type: ignore[misc]


class TestExecuteRanked:
    """Test GetFeedUseCase.execute_ranked method."""

    @pytest.mark.asyncio
    async def test_ranked_feed_returns_feed_output(self) -> None:
        """execute_ranked should return a FeedOutput instance."""
        posts = [
            _make_post(author_id=USER_1, hours_old=1.0, like_count=10, post_id=1),
            _make_post(author_id=USER_1, hours_old=2.0, like_count=5, post_id=2),
        ]
        feed_repo = FakeFeedRepo(posts)
        friend_repo = FakeFriendRepo({})
        history = FakeInteractionHistory()

        use_case = GetFeedUseCase(
            feed_repo=feed_repo, friend_repo=friend_repo,
            interaction_history=history,
        )

        result = await use_case.execute_ranked(
            GetRankedFeedInput(user_id=USER_1)
        )

        assert isinstance(result, FeedOutput)
        assert len(result.posts) == 2

    @pytest.mark.asyncio
    async def test_ranked_feed_orders_by_score(self) -> None:
        """Ranked mode should order posts by ranking score, not just time."""
        # Old post with high engagement should beat recent post with no engagement
        old_engaging = _make_post(
            author_id=USER_1, hours_old=12.0,
            like_count=100, comment_count=50, post_id=1,
        )
        new_boring = _make_post(
            author_id=USER_1, hours_old=0.5,
            like_count=0, comment_count=0, post_id=2,
        )
        feed_repo = FakeFeedRepo([new_boring, old_engaging])
        friend_repo = FakeFriendRepo({})
        history = FakeInteractionHistory()

        use_case = GetFeedUseCase(
            feed_repo=feed_repo, friend_repo=friend_repo,
            interaction_history=history,
        )

        result = await use_case.execute_ranked(
            GetRankedFeedInput(user_id=USER_1, mode="ranked")
        )

        # The old but engaging post should rank higher
        assert result.posts[0].id == str(old_engaging.id)

    @pytest.mark.asyncio
    async def test_chronological_mode_orders_by_time(self) -> None:
        """Chronological mode should order posts by time, ignoring engagement."""
        old_engaging = _make_post(
            author_id=USER_1, hours_old=12.0,
            like_count=100, comment_count=50, post_id=1,
        )
        new_boring = _make_post(
            author_id=USER_1, hours_old=0.5,
            like_count=0, comment_count=0, post_id=2,
        )
        feed_repo = FakeFeedRepo([old_engaging, new_boring])
        friend_repo = FakeFriendRepo({})
        history = FakeInteractionHistory()

        use_case = GetFeedUseCase(
            feed_repo=feed_repo, friend_repo=friend_repo,
            interaction_history=history,
        )

        result = await use_case.execute_ranked(
            GetRankedFeedInput(user_id=USER_1, mode="chronological")
        )

        # Newest first
        assert result.posts[0].id == str(new_boring.id)

    @pytest.mark.asyncio
    async def test_ranked_feed_respects_limit(self) -> None:
        """Ranked feed should respect the limit parameter."""
        posts = [
            _make_post(author_id=USER_1, hours_old=float(i), post_id=i)
            for i in range(1, 11)
        ]
        feed_repo = FakeFeedRepo(posts)
        friend_repo = FakeFriendRepo({})
        history = FakeInteractionHistory()

        use_case = GetFeedUseCase(
            feed_repo=feed_repo, friend_repo=friend_repo,
            interaction_history=history,
        )

        result = await use_case.execute_ranked(
            GetRankedFeedInput(user_id=USER_1, limit=3)
        )

        assert len(result.posts) == 3

    @pytest.mark.asyncio
    async def test_ranked_feed_fetches_larger_candidate_pool(self) -> None:
        """Should fetch more candidates than the final limit for better ranking."""
        posts = [
            _make_post(author_id=USER_1, hours_old=float(i), post_id=i)
            for i in range(1, 20)
        ]
        feed_repo = FakeFeedRepo(posts)
        friend_repo = FakeFriendRepo({})
        history = FakeInteractionHistory()

        use_case = GetFeedUseCase(
            feed_repo=feed_repo, friend_repo=friend_repo,
            interaction_history=history,
        )

        await use_case.execute_ranked(
            GetRankedFeedInput(user_id=USER_1, limit=5)
        )

        # Should have fetched more than 5 candidates for ranking
        assert feed_repo.last_limit is not None
        assert feed_repo.last_limit > 5

    @pytest.mark.asyncio
    async def test_ranked_feed_empty_returns_empty_result(self) -> None:
        """Empty feed should return empty FeedOutput."""
        feed_repo = FakeFeedRepo([])
        friend_repo = FakeFriendRepo({})
        history = FakeInteractionHistory()

        use_case = GetFeedUseCase(
            feed_repo=feed_repo, friend_repo=friend_repo,
            interaction_history=history,
        )

        result = await use_case.execute_ranked(
            GetRankedFeedInput(user_id=USER_1)
        )

        assert result.posts == []
        assert result.total_count == 0
        assert result.has_next_page is False

    @pytest.mark.asyncio
    async def test_ranked_feed_includes_friends_posts(self) -> None:
        """Ranked feed should include posts from friends."""
        user_post = _make_post(author_id=USER_1, hours_old=1.0, post_id=1)
        friend_post = _make_post(author_id=FRIEND_1, hours_old=0.5, post_id=2)

        feed_repo = FakeFeedRepo([user_post, friend_post])
        friend_repo = FakeFriendRepo({USER_1: [EntityId.from_str(FRIEND_1)]})
        history = FakeInteractionHistory()

        use_case = GetFeedUseCase(
            feed_repo=feed_repo, friend_repo=friend_repo,
            interaction_history=history,
        )

        result = await use_case.execute_ranked(
            GetRankedFeedInput(user_id=USER_1)
        )

        post_ids = [p.id for p in result.posts]
        assert str(user_post.id) in post_ids
        assert str(friend_post.id) in post_ids

    @pytest.mark.asyncio
    async def test_ranked_feed_with_affinity(self) -> None:
        """Posts from high-affinity authors should rank higher."""
        # Same recency and engagement, different affinity
        post_close = _make_post(
            author_id=FRIEND_1, hours_old=2.0, like_count=5, comment_count=2, post_id=1,
        )
        post_distant = _make_post(
            author_id=FRIEND_2, hours_old=2.0, like_count=5, comment_count=2, post_id=2,
        )

        feed_repo = FakeFeedRepo([post_close, post_distant])
        friend_repo = FakeFriendRepo({
            USER_1: [EntityId.from_str(FRIEND_1), EntityId.from_str(FRIEND_2)],
        })
        history = FakeInteractionHistory(
            interactions={
                (USER_1, FRIEND_1): (30, 15),  # high interaction
                (USER_1, FRIEND_2): (0, 0),  # no interaction
            }
        )

        use_case = GetFeedUseCase(
            feed_repo=feed_repo, friend_repo=friend_repo,
            interaction_history=history,
        )

        result = await use_case.execute_ranked(
            GetRankedFeedInput(user_id=USER_1, mode="ranked")
        )

        # Post from high-affinity friend should rank first
        assert result.posts[0].id == str(post_close.id)

    @pytest.mark.asyncio
    async def test_ranked_feed_has_next_page(self) -> None:
        """has_next_page should be True when more posts exist than limit."""
        posts = [
            _make_post(author_id=USER_1, hours_old=float(i), post_id=i)
            for i in range(1, 11)
        ]
        feed_repo = FakeFeedRepo(posts)
        friend_repo = FakeFriendRepo({})
        history = FakeInteractionHistory()

        use_case = GetFeedUseCase(
            feed_repo=feed_repo, friend_repo=friend_repo,
            interaction_history=history,
        )

        result = await use_case.execute_ranked(
            GetRankedFeedInput(user_id=USER_1, limit=3)
        )

        assert result.has_next_page is True
        assert result.total_count == 3  # page size (COUNT eliminated for perf)

    @pytest.mark.asyncio
    async def test_existing_execute_still_works(self) -> None:
        """Backward compatibility: existing execute method should still work."""
        from fb.application.post.feed_dtos import GetFeedInput

        posts = [
            _make_post(author_id=USER_1, hours_old=1.0, post_id=1),
        ]
        feed_repo = FakeFeedRepo(posts)
        friend_repo = FakeFriendRepo({})

        use_case = GetFeedUseCase(
            feed_repo=feed_repo, friend_repo=friend_repo,
        )

        result = await use_case.execute(GetFeedInput(user_id=USER_1))

        assert isinstance(result, FeedOutput)
        assert len(result.posts) == 1
