from __future__ import annotations

import strawberry

from fb.domain.shared.entity_id import EntityId
from fb.infrastructure.repositories.user_repo import SqlAlchemyUserRepository
from fb.presentation.graphql.context import GraphQLContext
from fb.presentation.graphql.types.auth import UserType


@strawberry.type
class AuthQuery:
    @strawberry.field
    async def me(self, info: strawberry.types.Info) -> UserType | None:
        ctx: GraphQLContext = info.context
        if not ctx.is_authenticated:
            return None

        container = ctx.container
        async with container.session_factory() as session:
            user_repo = SqlAlchemyUserRepository(session)
            user = await user_repo.find_by_id(
                EntityId.from_str(ctx.current_user_id)
            )

        if user is None:
            return None

        return UserType(
            id=strawberry.ID(str(user.id)),
            email=str(user.email),
            display_name=user.display_name,
            is_active=user.is_active,
        )
