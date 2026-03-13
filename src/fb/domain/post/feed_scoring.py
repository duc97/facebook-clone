from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from fb.domain.post.entities import Post


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    """Breakdown of individual scoring components for a feed post."""

    recency_score: float      # 0-40 points, exponential decay
    engagement_score: float   # 0-30 points, from likes/comments
    affinity_score: float     # 0-20 points, interaction frequency with author
    content_score: float      # 0-10 points, has media, content length


@dataclass(frozen=True, slots=True)
class ScoredPost:
    """A post together with its computed ranking score and breakdown."""

    post: Post
    score: float
    breakdown: ScoreBreakdown


# ── Constants ────────────────────────────────────────────────────────────────

_MAX_RECENCY: float = 40.0
_RECENCY_HALF_LIFE_HOURS: float = 24.0

_MAX_ENGAGEMENT: float = 30.0
_LIKE_WEIGHT: float = 1.0
_COMMENT_WEIGHT: float = 3.0
_ENGAGEMENT_NORMALIZER: float = 0.3  # scales raw points to fit within cap

_MAX_AFFINITY: float = 20.0
_DEFAULT_AFFINITY: float = 0.1  # baseline for unknown authors

_MAX_CONTENT: float = 10.0
_MEDIA_BONUS: float = 5.0
_LONG_CONTENT_THRESHOLD: int = 100
_LONG_CONTENT_BONUS: float = 5.0


class FeedScorer:
    """Pure domain logic for scoring and ranking feed posts.

    The scorer is stateless and has no external dependencies.
    All scoring factors are computed from post data and an optional
    affinities mapping.
    """

    def score_posts(
        self,
        posts: list[Post],
        affinities: dict[str, float],
    ) -> list[ScoredPost]:
        """Score a list of posts and return them sorted by score descending.

        Args:
            posts: Posts to score.
            affinities: Mapping of author_id (str) to affinity value (0.0–1.0).
                        Authors not present receive a small default.

        Returns:
            List of ScoredPost sorted by score descending.
        """
        if not posts:
            return []

        now = datetime.utcnow()
        scored = [self._score_single(post, affinities, now) for post in posts]
        scored.sort(key=lambda sp: sp.score, reverse=True)
        return scored

    # ── Private helpers ──────────────────────────────────────────────────

    def _score_single(
        self,
        post: Post,
        affinities: dict[str, float],
        now: datetime,
    ) -> ScoredPost:
        recency = self._recency_score(post, now)
        engagement = self._engagement_score(post)
        affinity = self._affinity_score(post, affinities)
        content = self._content_score(post)

        breakdown = ScoreBreakdown(
            recency_score=recency,
            engagement_score=engagement,
            affinity_score=affinity,
            content_score=content,
        )
        total = recency + engagement + affinity + content
        return ScoredPost(post=post, score=total, breakdown=breakdown)

    @staticmethod
    def _recency_score(post: Post, now: datetime) -> float:
        """Compute recency score: 40 * exp(-hours_old / 24).

        Posts with no created_at receive 0.
        """
        if post.created_at is None:
            return 0.0

        delta = now - post.created_at
        hours_old = max(delta.total_seconds() / 3600.0, 0.0)
        return _MAX_RECENCY * math.exp(-hours_old / _RECENCY_HALF_LIFE_HOURS)

    @staticmethod
    def _engagement_score(post: Post) -> float:
        """Compute engagement score: min(30, raw_score * normalizer).

        Raw score = like_count * 1 + comment_count * 3.
        """
        raw = post.like_count * _LIKE_WEIGHT + post.comment_count * _COMMENT_WEIGHT
        return min(_MAX_ENGAGEMENT, raw * _ENGAGEMENT_NORMALIZER)

    @staticmethod
    def _affinity_score(post: Post, affinities: dict[str, float]) -> float:
        """Compute affinity score based on user–author interaction history.

        Authors not in the affinities mapping receive a small default baseline.
        """
        author_key = str(post.author_id)
        affinity_value = affinities.get(author_key, _DEFAULT_AFFINITY)
        return _MAX_AFFINITY * affinity_value

    @staticmethod
    def _content_score(post: Post) -> float:
        """Compute content score: +5 for media, +5 for long content."""
        score = 0.0
        if post.media_urls:
            score += _MEDIA_BONUS
        if len(post.content) > _LONG_CONTENT_THRESHOLD:
            score += _LONG_CONTENT_BONUS
        return min(_MAX_CONTENT, score)
