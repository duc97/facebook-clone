from __future__ import annotations

from datetime import datetime
from typing import runtime_checkable

import pytest

from fb.domain.post.feed_cache_service import FeedCacheService
from fb.domain.post.feed_repository import FeedRepository
from fb.domain.shared.entity_id import EntityId


class TestFeedRepositoryProtocol:
    """Test that FeedRepository protocol is properly defined."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """FeedRepository should be runtime checkable."""
        assert runtime_checkable(FeedRepository)

    def test_protocol_has_get_feed_post_ids_method(self) -> None:
        """Protocol should have get_feed_post_ids method."""
        method = getattr(FeedRepository, "get_feed_post_ids", None)
        assert method is not None

    def test_protocol_has_get_feed_posts_method(self) -> None:
        """Protocol should have get_feed_posts method."""
        method = getattr(FeedRepository, "get_feed_posts", None)
        assert method is not None

    def test_protocol_has_get_feed_total_count_method(self) -> None:
        """Protocol should have get_feed_total_count method."""
        method = getattr(FeedRepository, "get_feed_total_count", None)
        assert method is not None


class TestFeedCacheServiceProtocol:
    """Test that FeedCacheService protocol is properly defined."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """FeedCacheService should be runtime checkable."""
        assert runtime_checkable(FeedCacheService)

    def test_protocol_has_get_feed_method(self) -> None:
        """Protocol should have get_feed method."""
        method = getattr(FeedCacheService, "get_feed", None)
        assert method is not None

    def test_protocol_has_set_feed_method(self) -> None:
        """Protocol should have set_feed method."""
        method = getattr(FeedCacheService, "set_feed", None)
        assert method is not None

    def test_protocol_has_invalidate_method(self) -> None:
        """Protocol should have invalidate method."""
        method = getattr(FeedCacheService, "invalidate", None)
        assert method is not None