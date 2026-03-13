from __future__ import annotations

from typing import Optional

import strawberry

from fb.application.profile.dtos import ProfileOutput
from fb.application.profile.get_profile import GetProfileUseCase
from fb.infrastructure.repositories.profile_repo import SqlAlchemyProfileRepository
from fb.infrastructure.repositories.user_repo import SqlAlchemyUserRepository
from fb.presentation.graphql.context import GraphQLContext
from fb.presentation.graphql.types.profile import ProfileType


@strawberry.type
class ProfileQuery:
    @strawberry.field
    async def profile(
        self, info: strawberry.types.Info, user_id: strawberry.ID
    ) -> Optional[ProfileType]:
        """Get a user's profile by user ID."""
        ctx: GraphQLContext = info.context
        container = ctx.container

        async with container.session_factory() as session:
            profile_repo = SqlAlchemyProfileRepository(session)
            user_repo = SqlAlchemyUserRepository(session)
            use_case = GetProfileUseCase(
                profile_repo=profile_repo,
                user_repo=user_repo,
            )
            result = await use_case.execute(str(user_id))

        if result is None:
            return None

        return _to_type(result)

    @strawberry.field
    async def my_profile(self, info: strawberry.types.Info) -> Optional[ProfileType]:
        """Get the authenticated user's profile."""
        ctx: GraphQLContext = info.context
        if not ctx.is_authenticated:
            return None

        container = ctx.container
        async with container.session_factory() as session:
            profile_repo = SqlAlchemyProfileRepository(session)
            user_repo = SqlAlchemyUserRepository(session)
            use_case = GetProfileUseCase(
                profile_repo=profile_repo,
                user_repo=user_repo,
            )
            result = await use_case.execute(ctx.current_user_id)  # type: ignore[arg-type]

        if result is None:
            return None

        return _to_type(result)


def _to_type(output: ProfileOutput) -> ProfileType:
    return ProfileType(
        id=strawberry.ID(output.id),
        user_id=strawberry.ID(output.user_id),
        bio=output.bio,
        avatar_url=output.avatar_url,
        cover_photo_url=output.cover_photo_url,
        location=output.location,
        website=output.website,
        display_name=output.display_name,
    )
