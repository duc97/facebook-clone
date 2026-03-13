from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SearchUsersInput:
    """Input DTO for searching users."""

    query: str
    limit: int = 20
    offset: int = 0


@dataclass(frozen=True, slots=True)
class UserSearchResult:
    """Single user result in a search response."""

    id: str
    email: str
    display_name: str
    is_active: bool


@dataclass(frozen=True, slots=True)
class SearchUsersOutput:
    """Output DTO for user search results."""

    users: list[UserSearchResult]
    total_count: int
    has_next_page: bool
