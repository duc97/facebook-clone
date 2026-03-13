from __future__ import annotations

from fb.application.auth.search_dtos import (
    SearchUsersInput,
    SearchUsersOutput,
    UserSearchResult,
)
from fb.domain.auth.search import UserSearchRepository


class SearchUsersUseCase:
    """Use case for searching users by display_name or email."""

    def __init__(self, search_repo: UserSearchRepository) -> None:
        self._search_repo = search_repo

    async def execute(self, input_data: SearchUsersInput) -> SearchUsersOutput:
        """Execute the search users use case.

        Validates input, delegates to the search repository, and maps
        the domain result to an output DTO.

        Raises:
            ValueError: If query is empty or whitespace-only.
        """
        query = input_data.query.strip()
        if not query:
            raise ValueError("Search query must not be empty")

        # Clamp limit to 1-100
        limit = max(1, min(input_data.limit, 100))

        # Clamp offset to >= 0
        offset = max(0, input_data.offset)

        cursor_page = await self._search_repo.search_users(
            query=query,
            limit=limit,
            offset=offset,
        )

        users = [
            UserSearchResult(
                id=str(user.id),
                email=str(user.email),
                display_name=user.display_name,
                is_active=user.is_active,
            )
            for user in cursor_page.items
        ]

        return SearchUsersOutput(
            users=users,
            total_count=cursor_page.total_count,
            has_next_page=cursor_page.page_info.has_next_page,
        )
