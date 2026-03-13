from __future__ import annotations

import pytest

from fb.application.auth.search_dtos import (
    SearchUsersInput,
    SearchUsersOutput,
    UserSearchResult,
)
from fb.application.auth.search_users import SearchUsersUseCase
from fb.domain.auth.entities import User
from fb.domain.auth.value_objects import Email, HashedPassword
from fb.domain.shared.entity_id import EntityId
from fb.domain.shared.pagination import CursorPage, PageInfo


# ─── Fake Repository ──────────────────────────────────────


class FakeUserSearchRepo:
    """In-memory fake implementing UserSearchRepository protocol."""

    def __init__(self, users: list[User]) -> None:
        self._users = users

    async def search_users(
        self, query: str, limit: int = 20, offset: int = 0
    ) -> CursorPage[User]:
        matched = [
            u
            for u in self._users
            if query.lower() in u.display_name.lower()
            or query.lower() in str(u.email).lower()
        ]
        total = len(matched)
        page = matched[offset : offset + limit]
        return CursorPage(
            items=tuple(page),
            page_info=PageInfo(
                has_next_page=offset + limit < total,
                has_previous_page=offset > 0,
            ),
            total_count=total,
        )


# ─── Helpers ──────────────────────────────────────────────


def _make_user(
    email: str = "test@example.com",
    name: str = "Test User",
    is_active: bool = True,
) -> User:
    return User(
        id=EntityId.generate(),
        email=Email(email),
        hashed_password=HashedPassword("hashed_pw"),
        display_name=name,
        is_active=is_active,
    )


def _sample_users() -> list[User]:
    return [
        _make_user(email="john@example.com", name="John Doe"),
        _make_user(email="jane@example.com", name="Jane Smith"),
        _make_user(email="bob@example.com", name="Bob Johnson"),
        _make_user(email="alice@example.com", name="Alice Williams"),
        _make_user(email="charlie@example.com", name="Charlie Brown"),
    ]


# ─── Fixtures ──────────────────────────────────────────────


@pytest.fixture
def users() -> list[User]:
    return _sample_users()


@pytest.fixture
def search_repo(users: list[User]) -> FakeUserSearchRepo:
    return FakeUserSearchRepo(users)


@pytest.fixture
def use_case(search_repo: FakeUserSearchRepo) -> SearchUsersUseCase:
    return SearchUsersUseCase(search_repo)


# ─── Tests ──────────────────────────────────────────────


class TestSearchUsersUseCase:
    async def test_search_by_display_name(
        self, use_case: SearchUsersUseCase
    ) -> None:
        """Searching by display name should find matching users."""
        result = await use_case.execute(SearchUsersInput(query="John"))
        assert isinstance(result, SearchUsersOutput)
        assert len(result.users) == 2  # John Doe + Bob Johnson
        names = [u.display_name for u in result.users]
        assert "John Doe" in names
        assert "Bob Johnson" in names

    async def test_search_by_email(
        self, use_case: SearchUsersUseCase
    ) -> None:
        """Searching by email should find matching users."""
        result = await use_case.execute(SearchUsersInput(query="alice@"))
        assert len(result.users) == 1
        assert result.users[0].email == "alice@example.com"

    async def test_search_case_insensitive(
        self, use_case: SearchUsersUseCase
    ) -> None:
        """Search should be case-insensitive."""
        result_lower = await use_case.execute(SearchUsersInput(query="john"))
        result_upper = await use_case.execute(SearchUsersInput(query="JOHN"))
        assert len(result_lower.users) == len(result_upper.users)
        assert len(result_lower.users) == 2  # John Doe + Bob Johnson

    async def test_search_no_results(
        self, use_case: SearchUsersUseCase
    ) -> None:
        """Searching for a non-matching query should return empty."""
        result = await use_case.execute(SearchUsersInput(query="zzzznonexistent"))
        assert len(result.users) == 0
        assert result.total_count == 0
        assert result.has_next_page is False

    async def test_search_empty_query_raises(
        self, use_case: SearchUsersUseCase
    ) -> None:
        """Empty query should raise ValueError."""
        with pytest.raises(ValueError, match="query"):
            await use_case.execute(SearchUsersInput(query=""))

    async def test_search_whitespace_query_raises(
        self, use_case: SearchUsersUseCase
    ) -> None:
        """Whitespace-only query should raise ValueError."""
        with pytest.raises(ValueError, match="query"):
            await use_case.execute(SearchUsersInput(query="   "))

    async def test_search_pagination(
        self, use_case: SearchUsersUseCase
    ) -> None:
        """Limit and offset should control pagination."""
        # All users match "example.com"
        result_page1 = await use_case.execute(
            SearchUsersInput(query="example.com", limit=2, offset=0)
        )
        result_page2 = await use_case.execute(
            SearchUsersInput(query="example.com", limit=2, offset=2)
        )
        assert len(result_page1.users) == 2
        assert len(result_page2.users) == 2
        assert result_page1.total_count == 5
        assert result_page2.total_count == 5
        # Pages should have different users
        ids_page1 = {u.id for u in result_page1.users}
        ids_page2 = {u.id for u in result_page2.users}
        assert ids_page1.isdisjoint(ids_page2)

    async def test_search_limit_clamped(self) -> None:
        """Limit > 100 should be clamped to 100."""
        users = [_make_user(email=f"user{i}@example.com", name=f"User {i}") for i in range(5)]
        repo = FakeUserSearchRepo(users)
        use_case = SearchUsersUseCase(repo)
        # Should not raise, limit gets clamped to 100
        result = await use_case.execute(
            SearchUsersInput(query="User", limit=500)
        )
        assert len(result.users) == 5  # only 5 users exist
        assert result.total_count == 5

    async def test_search_has_next_page(
        self, use_case: SearchUsersUseCase
    ) -> None:
        """has_next_page should be True when more results exist beyond current page."""
        # All 5 users match "example.com", request only 2
        result = await use_case.execute(
            SearchUsersInput(query="example.com", limit=2, offset=0)
        )
        assert result.has_next_page is True

        # Request the last page
        result_last = await use_case.execute(
            SearchUsersInput(query="example.com", limit=2, offset=4)
        )
        assert result_last.has_next_page is False

    async def test_search_negative_offset_clamped(self) -> None:
        """Negative offset should be clamped to 0."""
        users = [_make_user(email="a@example.com", name="Alpha")]
        repo = FakeUserSearchRepo(users)
        use_case = SearchUsersUseCase(repo)
        result = await use_case.execute(
            SearchUsersInput(query="Alpha", limit=10, offset=-5)
        )
        assert len(result.users) == 1

    async def test_search_output_maps_user_fields(
        self, use_case: SearchUsersUseCase
    ) -> None:
        """Output should correctly map User entity fields to UserSearchResult."""
        result = await use_case.execute(SearchUsersInput(query="Jane"))
        assert len(result.users) == 1
        user_result = result.users[0]
        assert isinstance(user_result, UserSearchResult)
        assert user_result.email == "jane@example.com"
        assert user_result.display_name == "Jane Smith"
        assert user_result.is_active is True
        # id should be a string representation of the UUID
        assert len(user_result.id) > 0
