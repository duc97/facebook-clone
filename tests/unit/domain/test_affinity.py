from __future__ import annotations

import uuid

import pytest

from fb.domain.post.affinity import AffinityCalculator, InteractionHistoryProvider
from fb.domain.shared.entity_id import EntityId


# ── Helpers ──────────────────────────────────────────────────────────────────


def _uuid(n: int) -> str:
    return str(uuid.UUID(int=n))


USER_1 = _uuid(1)
AUTHOR_1 = _uuid(10)
AUTHOR_2 = _uuid(20)
AUTHOR_3 = _uuid(30)


class FakeInteractionHistory:
    """Fake implementation of InteractionHistoryProvider for testing."""

    def __init__(
        self,
        interactions: dict[tuple[str, str], tuple[int, int]] | None = None,
    ) -> None:
        # Key: (user_id, author_id), Value: (like_count, comment_count)
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


# ── Tests ────────────────────────────────────────────────────────────────────


class TestAffinityCalculator:
    """Test AffinityCalculator behavior."""

    def test_no_interactions_returns_zero_affinity(self) -> None:
        """User with zero interactions should have zero affinity."""
        calc = AffinityCalculator()
        affinity = calc.calculate_affinity(likes=0, comments=0)

        assert affinity == 0.0

    def test_high_interactions_returns_high_affinity(self) -> None:
        """User with many interactions should have high affinity (close to 1.0)."""
        calc = AffinityCalculator()
        affinity = calc.calculate_affinity(likes=100, comments=50)

        assert affinity >= 0.8
        assert affinity <= 1.0

    def test_affinity_never_exceeds_one(self) -> None:
        """Affinity should be capped at 1.0."""
        calc = AffinityCalculator()
        affinity = calc.calculate_affinity(likes=10000, comments=5000)

        assert affinity <= 1.0

    def test_affinity_never_negative(self) -> None:
        """Affinity should never be negative."""
        calc = AffinityCalculator()
        affinity = calc.calculate_affinity(likes=0, comments=0)

        assert affinity >= 0.0

    def test_comments_contribute_more_than_likes(self) -> None:
        """Comments should produce higher affinity than equivalent likes."""
        calc = AffinityCalculator()
        affinity_likes = calc.calculate_affinity(likes=10, comments=0)
        affinity_comments = calc.calculate_affinity(likes=0, comments=10)

        assert affinity_comments > affinity_likes

    def test_moderate_interactions_give_moderate_affinity(self) -> None:
        """A few interactions should give a moderate affinity score."""
        calc = AffinityCalculator()
        affinity = calc.calculate_affinity(likes=5, comments=2)

        assert affinity > 0.0
        assert affinity < 1.0

    @pytest.mark.asyncio
    async def test_compute_affinities_from_history(self) -> None:
        """Should compute affinities for multiple authors from interaction history."""
        history = FakeInteractionHistory(
            interactions={
                (USER_1, AUTHOR_1): (20, 10),  # high interaction
                (USER_1, AUTHOR_2): (1, 0),  # low interaction
                # AUTHOR_3 not present → (0, 0)
            }
        )

        calc = AffinityCalculator()
        author_ids = [
            EntityId.from_str(AUTHOR_1),
            EntityId.from_str(AUTHOR_2),
            EntityId.from_str(AUTHOR_3),
        ]

        affinities = await calc.compute_affinities(
            user_id=EntityId.from_str(USER_1),
            author_ids=author_ids,
            history_provider=history,
        )

        assert affinities[AUTHOR_1] > affinities[AUTHOR_2]
        assert affinities[AUTHOR_2] > affinities[AUTHOR_3]
        assert affinities[AUTHOR_3] == 0.0

    @pytest.mark.asyncio
    async def test_compute_affinities_empty_authors(self) -> None:
        """Should return empty dict for empty author list."""
        history = FakeInteractionHistory()
        calc = AffinityCalculator()

        affinities = await calc.compute_affinities(
            user_id=EntityId.from_str(USER_1),
            author_ids=[],
            history_provider=history,
        )

        assert affinities == {}


class TestInteractionHistoryProviderProtocol:
    """Test that InteractionHistoryProvider protocol is properly defined."""

    def test_protocol_has_get_interaction_counts(self) -> None:
        """Protocol should have get_interaction_counts method."""
        method = getattr(InteractionHistoryProvider, "get_interaction_counts", None)
        assert method is not None

    def test_protocol_has_get_batch_interaction_counts(self) -> None:
        """Protocol should have get_batch_interaction_counts method."""
        method = getattr(InteractionHistoryProvider, "get_batch_interaction_counts", None)
        assert method is not None

    def test_fake_implements_protocol(self) -> None:
        """FakeInteractionHistory should satisfy the protocol."""
        fake = FakeInteractionHistory()
        assert isinstance(fake, InteractionHistoryProvider)
