from __future__ import annotations

import math
from typing import Protocol, runtime_checkable

from fb.domain.shared.entity_id import EntityId


@runtime_checkable
class InteractionHistoryProvider(Protocol):
    """Protocol for retrieving interaction counts between users."""

    async def get_interaction_counts(
        self, user_id: EntityId, author_id: EntityId
    ) -> tuple[int, int]:
        """Get (like_count, comment_count) for user's interactions on author's posts."""
        ...

    async def get_batch_interaction_counts(
        self, user_id: EntityId, author_ids: list[EntityId]
    ) -> dict[str, tuple[int, int]]:
        """Get interaction counts for multiple authors at once.

        Returns dict mapping author_id (str) to (like_count, comment_count).
        """
        ...


# ── Constants ────────────────────────────────────────────────────────────────

_LIKE_WEIGHT: float = 1.0
_COMMENT_WEIGHT: float = 3.0
_SATURATION_THRESHOLD: float = 50.0  # interactions at which affinity approaches 1.0


class AffinityCalculator:
    """Calculates user-to-author affinity based on interaction history.

    Affinity is a float in [0.0, 1.0] representing how closely a user
    interacts with a given author. Higher values mean more frequent
    interactions.

    The formula uses a saturating function:
        affinity = 1 - exp(-weighted_sum / threshold)

    This ensures affinity rises quickly with early interactions and
    saturates smoothly toward 1.0.
    """

    def calculate_affinity(self, likes: int, comments: int) -> float:
        """Calculate affinity from raw interaction counts.

        Args:
            likes: Number of likes the user has given to the author's posts.
            comments: Number of comments the user has left on the author's posts.

        Returns:
            Affinity value in [0.0, 1.0].
        """
        weighted = likes * _LIKE_WEIGHT + comments * _COMMENT_WEIGHT
        if weighted <= 0:
            return 0.0
        return min(1.0, 1.0 - math.exp(-weighted / _SATURATION_THRESHOLD))

    async def compute_affinities(
        self,
        user_id: EntityId,
        author_ids: list[EntityId],
        history_provider: InteractionHistoryProvider,
    ) -> dict[str, float]:
        """Compute affinities for multiple authors using a history provider.

        Args:
            user_id: The user whose affinities to compute.
            author_ids: List of author EntityIds.
            history_provider: Provider for interaction counts.

        Returns:
            Dict mapping author_id (str) to affinity (0.0–1.0).
        """
        if not author_ids:
            return {}

        counts = await history_provider.get_batch_interaction_counts(
            user_id, author_ids
        )

        affinities: dict[str, float] = {}
        for aid in author_ids:
            key = str(aid)
            likes, comments = counts.get(key, (0, 0))
            affinities[key] = self.calculate_affinity(likes, comments)

        return affinities
