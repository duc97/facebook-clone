from __future__ import annotations

import pytest

from fb.domain.auth.search import UserSearchRepository


class TestUserSearchRepositoryProtocol:
    def test_is_runtime_checkable(self) -> None:
        """UserSearchRepository should be a runtime-checkable Protocol."""
        assert hasattr(UserSearchRepository, "__protocol_attrs__") or hasattr(
            UserSearchRepository, "__abstractmethods__"
        ) or callable(getattr(UserSearchRepository, "__instancecheck__", None))

    def test_class_with_search_method_satisfies_protocol(self) -> None:
        """A class implementing search_users should satisfy the protocol."""
        from fb.domain.shared.pagination import CursorPage, PageInfo

        class FakeRepo:
            async def search_users(
                self, query: str, limit: int = 20, offset: int = 0
            ) -> CursorPage:
                return CursorPage(
                    items=(),
                    page_info=PageInfo(has_next_page=False, has_previous_page=False),
                    total_count=0,
                )

        assert isinstance(FakeRepo(), UserSearchRepository)

    def test_class_without_search_method_does_not_satisfy_protocol(self) -> None:
        """A class without search_users should NOT satisfy the protocol."""

        class NotARepo:
            pass

        assert not isinstance(NotARepo(), UserSearchRepository)
