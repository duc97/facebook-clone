from __future__ import annotations

from datetime import datetime

from fb.application.post.feed_dtos import (
    FeedCursorOutput,
    FeedOutput,
    FeedPostOutput,
    GetFeedCursorInput,
    GetFeedInput,
    GetRankedFeedInput,
)
from fb.domain.follow.repository import FollowRepository
from fb.domain.post.affinity import AffinityCalculator, InteractionHistoryProvider
from fb.domain.post.entities import Post
from fb.domain.post.feed_cache_service import FeedCacheService
from fb.domain.post.feed_repository import FeedRepository as FeedRepo
from fb.domain.post.feed_scoring import FeedScorer
from fb.domain.shared.entity_id import EntityId

# ── Constants ────────────────────────────────────────────────────────────────

_CANDIDATE_MULTIPLIER: int = 3  # fetch N * limit candidates for ranking


class GetFeedUseCase:
    """Use case for retrieving user's feed."""

    def __init__(
        self,
        feed_repo: FeedRepo,
        follow_repo: FollowRepository,
        feed_cache: FeedCacheService | None = None,
        interaction_history: InteractionHistoryProvider | None = None,
    ) -> None:
        self._feed_repo = feed_repo
        self._follow_repo = follow_repo
        self._feed_cache = feed_cache
        self._interaction_history = interaction_history
        self._scorer = FeedScorer()
        self._affinity_calc = AffinityCalculator()

    async def execute(self, input_data: GetFeedInput) -> FeedOutput:
        """Execute the get feed use case (chronological, backward-compatible)."""
        user_id = EntityId.from_str(input_data.user_id)
        limit = min(max(input_data.limit, 1), 50)
        offset = max(input_data.offset, 0)

        # Get user's friends
        friend_ids = await self._follow_repo.get_following(user_id, limit=1000)

        # Fetch limit+1 to detect has_next_page without a separate COUNT query
        post_ids = await self._feed_repo.get_feed_post_ids(
            user_id=user_id, friend_ids=friend_ids, limit=limit + 1, offset=offset
        )

        if not post_ids:
            return FeedOutput(posts=[], total_count=0, has_next_page=False)

        has_next = len(post_ids) > limit
        page_ids = post_ids[:limit]

        # Fetch the actual posts
        posts = await self._feed_repo.get_feed_posts(page_ids)

        return FeedOutput(
            posts=[self._to_output(p) for p in posts],
            total_count=len(posts),
            has_next_page=has_next,
        )

    async def execute_ranked(self, input_data: GetRankedFeedInput) -> FeedOutput:
        """Execute the get feed use case with optional ranking.

        Steps:
          1. Get friend IDs
          2. Fetch candidate posts (larger pool for ranking)
          3. Compute affinities from interaction history
          4. Score with FeedScorer (or sort chronologically)
          5. Slice to requested limit
          6. Return FeedOutput
        """
        user_id = EntityId.from_str(input_data.user_id)
        limit = min(max(input_data.limit, 1), 50)

        # 1. Get user's friends
        friend_ids = await self._follow_repo.get_following(user_id, limit=1000)

        # 2. Fetch candidate pool (larger than final limit for better ranking)
        candidate_limit = limit * _CANDIDATE_MULTIPLIER
        post_ids = await self._feed_repo.get_feed_post_ids(
            user_id=user_id, friend_ids=friend_ids, limit=candidate_limit, offset=0
        )

        if not post_ids:
            return FeedOutput(posts=[], total_count=0, has_next_page=False)

        candidates = await self._feed_repo.get_feed_posts(post_ids)

        # Estimate has_next_page from candidate pool size instead of
        # running a separate COUNT(*) query on every request.
        # The candidate pool fetches limit * 3 rows — if we got that many,
        # there are likely more posts available.
        has_more = len(candidates) >= candidate_limit

        if input_data.mode == "chronological":
            # Sort by created_at descending (chronological order)
            sorted_posts = sorted(
                candidates,
                key=lambda p: p.created_at or datetime.min,
                reverse=True,
            )
            final_posts = sorted_posts[:limit]
        else:
            # 3. Compute affinities
            affinities = await self._compute_affinities(user_id, candidates)

            # 4. Score and rank
            scored = self._scorer.score_posts(candidates, affinities)

            # 5. Slice to limit
            final_posts = [sp.post for sp in scored[:limit]]

        return FeedOutput(
            posts=[self._to_output(p) for p in final_posts],
            total_count=len(final_posts),
            has_next_page=has_more,
        )

    async def execute_cursor(self, input_data: GetFeedCursorInput) -> FeedCursorOutput:
        """Execute the get feed use case with cursor-based pagination."""
        user_id = EntityId.from_str(input_data.user_id)
        first = min(max(input_data.first, 1), 50)

        # Get user's friends
        friend_ids = await self._follow_repo.get_following(user_id, limit=1000)

        # Get feed posts using cursor pagination
        cursor_page = await self._feed_repo.get_feed_posts_cursor(
            user_id=user_id, friend_ids=friend_ids,
            first=first, after_cursor=input_data.after
        )

        return FeedCursorOutput(
            posts=[self._to_output(p) for p in cursor_page.items],
            page_info={
                "has_next_page": cursor_page.page_info.has_next_page,
                "has_previous_page": cursor_page.page_info.has_previous_page,
                "start_cursor": cursor_page.page_info.start_cursor,
                "end_cursor": cursor_page.page_info.end_cursor,
            },
            total_count=cursor_page.total_count,
        )

    # ── Private helpers ──────────────────────────────────────────────────

    async def _compute_affinities(
        self, user_id: EntityId, posts: list[Post]
    ) -> dict[str, float]:
        """Compute affinities for all unique authors in the candidate posts."""
        if self._interaction_history is None:
            return {}

        # Collect unique author IDs
        unique_authors = list({p.author_id for p in posts})

        return await self._affinity_calc.compute_affinities(
            user_id=user_id,
            author_ids=unique_authors,
            history_provider=self._interaction_history,
        )

    @staticmethod
    def _to_output(post: Post) -> FeedPostOutput:
        """Convert Post entity to FeedPostOutput DTO."""
        return FeedPostOutput(
            id=str(post.id),
            author_id=str(post.author_id),
            content=post.content,
            media_urls=list(post.media_urls),
            like_count=post.like_count,
            comment_count=post.comment_count,
            created_at=str(post.created_at) if post.created_at else None,
        )
