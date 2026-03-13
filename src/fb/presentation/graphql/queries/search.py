from __future__ import annotations

import strawberry

from fb.application.auth.search_dtos import SearchUsersInput
from fb.application.auth.search_users import SearchUsersUseCase
from fb.infrastructure.repositories.user_search_repo import SqlAlchemyUserSearchRepository
from fb.presentation.graphql.context import GraphQLContext
from fb.presentation.graphql.types.pagination import UserSearchResponse, UserSearchResultType


@strawberry.type
class SearchQuery:
    """GraphQL query type for user search."""

    @strawberry.field
    async def search_users(
        self,
        info: strawberry.types.Info,
        query: str,
        limit: int = 20,
        offset: int = 0,
    ) -> UserSearchResponse:
        """Search users by display name or email."""
        ctx: GraphQLContext = info.context
        container = ctx.container

        async with container.session_factory() as session:
            search_repo = SqlAlchemyUserSearchRepository(session)
            use_case = SearchUsersUseCase(search_repo)
            result = await use_case.execute(
                SearchUsersInput(query=query, limit=limit, offset=offset)
            )

        return UserSearchResponse(
            users=[
                UserSearchResultType(
                    id=strawberry.ID(u.id),
                    email=u.email,
                    display_name=u.display_name,
                    is_active=u.is_active,
                )
                for u in result.users
            ],
            total_count=result.total_count,
            has_next_page=result.has_next_page,
        )
