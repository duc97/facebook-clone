from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta

import pytest

from fb.domain.post.entities import Post
from fb.domain.post.feed_scoring import FeedScorer, ScoreBreakdown, ScoredPost
from fb.domain.shared.entity_id import EntityId


# ── Helpers ──────────────────────────────────────────────────────────────────


def _uuid(n: int) -> str:
    """Generate a deterministic UUID from an integer for test reproducibility."""
    return str(uuid.UUID(int=n))


def _make_post(
    *,
    hours_old: float = 0.5,
    like_count: int = 0,
    comment_count: int = 0,
    media_urls: tuple[str, ...] = (),
    content: str = "Test content",
    author_id: str | None = None,
    post_id: int = 1,
) -> Post:
    """Create a Post entity for testing with controlled age."""
    created_at = datetime.utcnow() - timedelta(hours=hours_old)
    return Post(
        id=EntityId.from_str(_uuid(post_id)),
        author_id=EntityId.from_str(author_id or _uuid(100)),
        content=content,
        media_urls=media_urls,
        like_count=like_count,
        comment_count=comment_count,
        is_published=True,
        created_at=created_at,
    )


# ── Recency Scoring Tests ───────────────────────────────────────────────────


class TestRecencyScoring:
    """Test the recency component of feed scoring."""

    def test_recent_post_gets_high_recency_score(self) -> None:
        """A post less than 1 hour old should score close to 40."""
        post = _make_post(hours_old=0.5)
        scorer = FeedScorer()

        scored = scorer.score_posts([post], affinities={})

        assert len(scored) == 1
        assert scored[0].breakdown.recency_score >= 38.0
        assert scored[0].breakdown.recency_score <= 40.0

    def test_day_old_post_gets_medium_recency_score(self) -> None:
        """A 24-hour-old post should score roughly 40 * exp(-1) ~ 14.7."""
        post = _make_post(hours_old=24.0)
        scorer = FeedScorer()

        scored = scorer.score_posts([post], affinities={})

        expected = 40 * math.exp(-24.0 / 24)
        assert abs(scored[0].breakdown.recency_score - expected) < 1.0

    def test_two_day_old_post_gets_low_recency_score(self) -> None:
        """A 48-hour-old post should score roughly 40 * exp(-2) ~ 5.4."""
        post = _make_post(hours_old=48.0)
        scorer = FeedScorer()

        scored = scorer.score_posts([post], affinities={})

        expected = 40 * math.exp(-48.0 / 24)
        assert abs(scored[0].breakdown.recency_score - expected) < 1.0

    def test_very_old_post_gets_near_zero_recency(self) -> None:
        """A post that is a week old should have near-zero recency."""
        post = _make_post(hours_old=168.0)
        scorer = FeedScorer()

        scored = scorer.score_posts([post], affinities={})

        assert scored[0].breakdown.recency_score < 1.0

    def test_post_with_no_created_at_gets_zero_recency(self) -> None:
        """A post with None created_at should get zero recency score."""
        post = Post(
            id=EntityId.from_str(_uuid(1)),
            author_id=EntityId.from_str(_uuid(100)),
            content="Test",
            media_urls=(),
            like_count=0,
            comment_count=0,
            is_published=True,
            created_at=None,
        )
        scorer = FeedScorer()

        scored = scorer.score_posts([post], affinities={})

        assert scored[0].breakdown.recency_score == 0.0


# ── Engagement Scoring Tests ────────────────────────────────────────────────


class TestEngagementScoring:
    """Test the engagement component of feed scoring."""

    def test_post_with_no_engagement_gets_zero(self) -> None:
        """A post with 0 likes and 0 comments should get 0 engagement."""
        post = _make_post(like_count=0, comment_count=0)
        scorer = FeedScorer()

        scored = scorer.score_posts([post], affinities={})

        assert scored[0].breakdown.engagement_score == 0.0

    def test_post_with_many_likes_gets_high_engagement(self) -> None:
        """A post with many likes should get a high engagement score."""
        post = _make_post(like_count=50, comment_count=0)
        scorer = FeedScorer()

        scored = scorer.score_posts([post], affinities={})

        assert scored[0].breakdown.engagement_score >= 15.0

    def test_comments_weighted_more_than_likes(self) -> None:
        """Comments should contribute more to engagement than likes (3x weight)."""
        post_likes = _make_post(like_count=10, comment_count=0, post_id=1)
        post_comments = _make_post(like_count=0, comment_count=10, post_id=2)
        scorer = FeedScorer()

        scored_likes = scorer.score_posts([post_likes], affinities={})
        scored_comments = scorer.score_posts([post_comments], affinities={})

        assert (
            scored_comments[0].breakdown.engagement_score
            > scored_likes[0].breakdown.engagement_score
        )

    def test_engagement_score_capped_at_30(self) -> None:
        """Engagement score should never exceed 30."""
        post = _make_post(like_count=1000, comment_count=500)
        scorer = FeedScorer()

        scored = scorer.score_posts([post], affinities={})

        assert scored[0].breakdown.engagement_score <= 30.0

    def test_moderate_engagement_scores_reasonably(self) -> None:
        """A post with moderate engagement should get a mid-range score."""
        post = _make_post(like_count=5, comment_count=2)
        scorer = FeedScorer()

        scored = scorer.score_posts([post], affinities={})

        # 5*1 + 2*3 = 11 raw points
        assert scored[0].breakdown.engagement_score > 0.0
        assert scored[0].breakdown.engagement_score <= 30.0


# ── Affinity Scoring Tests ──────────────────────────────────────────────────


class TestAffinityScoring:
    """Test the affinity component of feed scoring."""

    def test_high_affinity_author_gets_high_score(self) -> None:
        """A post from an author with high affinity should score high."""
        author_id = _uuid(200)
        post = _make_post(author_id=author_id)
        scorer = FeedScorer()

        scored = scorer.score_posts([post], affinities={author_id: 1.0})

        assert scored[0].breakdown.affinity_score >= 18.0
        assert scored[0].breakdown.affinity_score <= 20.0

    def test_zero_affinity_author_gets_zero(self) -> None:
        """A post from an author with zero affinity should get 0."""
        author_id = _uuid(200)
        post = _make_post(author_id=author_id)
        scorer = FeedScorer()

        scored = scorer.score_posts([post], affinities={author_id: 0.0})

        assert scored[0].breakdown.affinity_score == 0.0

    def test_unknown_author_gets_default_affinity(self) -> None:
        """A post from an author not in affinities dict should get a small baseline."""
        post = _make_post(author_id=_uuid(999))
        scorer = FeedScorer()

        scored = scorer.score_posts([post], affinities={})

        # Unknown author should get a small default, not zero
        assert scored[0].breakdown.affinity_score >= 0.0
        assert scored[0].breakdown.affinity_score <= 5.0

    def test_medium_affinity_gives_proportional_score(self) -> None:
        """Affinity 0.5 should give roughly half the max score."""
        author_id = _uuid(200)
        post = _make_post(author_id=author_id)
        scorer = FeedScorer()

        scored = scorer.score_posts([post], affinities={author_id: 0.5})

        assert scored[0].breakdown.affinity_score >= 8.0
        assert scored[0].breakdown.affinity_score <= 12.0


# ── Content Scoring Tests ───────────────────────────────────────────────────


class TestContentScoring:
    """Test the content component of feed scoring."""

    def test_post_with_media_gets_bonus(self) -> None:
        """A post with media should get +5 content score."""
        post_with_media = _make_post(
            media_urls=("https://example.com/img.jpg",),
            content="Short",
            post_id=1,
        )
        post_without_media = _make_post(
            media_urls=(),
            content="Short",
            post_id=2,
        )
        scorer = FeedScorer()

        scored_with = scorer.score_posts([post_with_media], affinities={})
        scored_without = scorer.score_posts([post_without_media], affinities={})

        diff = (
            scored_with[0].breakdown.content_score
            - scored_without[0].breakdown.content_score
        )
        assert diff == pytest.approx(5.0)

    def test_long_content_gets_bonus(self) -> None:
        """A post with content > 100 chars should get +5 content score."""
        short_content = "Short"
        long_content = "A" * 101
        post_long = _make_post(content=long_content, post_id=1)
        post_short = _make_post(content=short_content, post_id=2)
        scorer = FeedScorer()

        scored_long = scorer.score_posts([post_long], affinities={})
        scored_short = scorer.score_posts([post_short], affinities={})

        diff = (
            scored_long[0].breakdown.content_score
            - scored_short[0].breakdown.content_score
        )
        assert diff == pytest.approx(5.0)

    def test_content_score_max_is_10(self) -> None:
        """Max content score should be 10 (media + long content)."""
        post = _make_post(
            media_urls=("https://example.com/img.jpg",),
            content="A" * 150,
        )
        scorer = FeedScorer()

        scored = scorer.score_posts([post], affinities={})

        assert scored[0].breakdown.content_score == pytest.approx(10.0)

    def test_no_media_and_short_content_scores_zero(self) -> None:
        """A post with no media and short content should get 0 content score."""
        post = _make_post(media_urls=(), content="Hi")
        scorer = FeedScorer()

        scored = scorer.score_posts([post], affinities={})

        assert scored[0].breakdown.content_score == pytest.approx(0.0)


# ── Overall Scoring & Sorting Tests ─────────────────────────────────────────


class TestOverallScoring:
    """Test the combined scoring and sorting behavior."""

    def test_posts_sorted_by_score_descending(self) -> None:
        """Posts should be returned sorted by total score, highest first."""
        # Recent, high engagement
        great_post = _make_post(hours_old=0.5, like_count=50, comment_count=20, post_id=1)
        # Old, no engagement
        bad_post = _make_post(hours_old=72.0, like_count=0, comment_count=0, post_id=2)
        # Medium
        ok_post = _make_post(hours_old=12.0, like_count=5, comment_count=2, post_id=3)

        scorer = FeedScorer()
        scored = scorer.score_posts([bad_post, ok_post, great_post], affinities={})

        assert scored[0].post.id == great_post.id
        assert scored[2].post.id == bad_post.id

    def test_score_breakdown_sums_to_total(self) -> None:
        """The total score should be the sum of all breakdown components."""
        post = _make_post(
            hours_old=6.0,
            like_count=10,
            comment_count=5,
            media_urls=("https://example.com/img.jpg",),
            content="A" * 150,
            author_id=_uuid(200),
        )
        scorer = FeedScorer()

        scored = scorer.score_posts([post], affinities={_uuid(200): 0.7})
        result = scored[0]

        expected_total = (
            result.breakdown.recency_score
            + result.breakdown.engagement_score
            + result.breakdown.affinity_score
            + result.breakdown.content_score
        )
        assert result.score == pytest.approx(expected_total)

    def test_empty_post_list_returns_empty(self) -> None:
        """Scoring an empty list should return an empty list."""
        scorer = FeedScorer()

        scored = scorer.score_posts([], affinities={})

        assert scored == []

    def test_total_score_never_exceeds_100(self) -> None:
        """Total score should never exceed 100 (40+30+20+10)."""
        post = _make_post(
            hours_old=0.01,
            like_count=1000,
            comment_count=500,
            media_urls=("https://example.com/img.jpg",),
            content="A" * 200,
            author_id=_uuid(200),
        )
        scorer = FeedScorer()

        scored = scorer.score_posts([post], affinities={_uuid(200): 1.0})

        assert scored[0].score <= 100.0

    def test_scored_post_preserves_original_post(self) -> None:
        """ScoredPost should contain the original Post entity unchanged."""
        post = _make_post(like_count=10, comment_count=5)
        scorer = FeedScorer()

        scored = scorer.score_posts([post], affinities={})

        assert scored[0].post is post
        assert scored[0].post.like_count == 10
        assert scored[0].post.comment_count == 5


# ── Score Dataclass Tests ────────────────────────────────────────────────────


class TestScoredPostDataclass:
    """Test that ScoredPost and ScoreBreakdown are proper frozen dataclasses."""

    def test_score_breakdown_is_frozen(self) -> None:
        """ScoreBreakdown should be immutable."""
        breakdown = ScoreBreakdown(
            recency_score=30.0,
            engagement_score=20.0,
            affinity_score=15.0,
            content_score=10.0,
        )
        with pytest.raises(AttributeError):
            breakdown.recency_score = 0.0  # type: ignore[misc]

    def test_scored_post_is_frozen(self) -> None:
        """ScoredPost should be immutable."""
        post = _make_post()
        breakdown = ScoreBreakdown(
            recency_score=30.0,
            engagement_score=20.0,
            affinity_score=15.0,
            content_score=10.0,
        )
        scored = ScoredPost(post=post, score=75.0, breakdown=breakdown)
        with pytest.raises(AttributeError):
            scored.score = 0.0  # type: ignore[misc]
