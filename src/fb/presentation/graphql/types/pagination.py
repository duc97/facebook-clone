from __future__ import annotations

import strawberry


@strawberry.type
class PageInfoType:
    """GraphQL type for pagination info."""

    has_next_page: bool
    has_previous_page: bool


@strawberry.type
class UserSearchResultType:
    """GraphQL type for a single user search result."""

    id: strawberry.ID
    email: str
    display_name: str
    is_active: bool


@strawberry.type
class UserSearchResponse:
    """GraphQL type for the user search response."""

    users: list[UserSearchResultType]
    total_count: int
    has_next_page: bool
