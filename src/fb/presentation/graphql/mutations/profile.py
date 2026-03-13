from __future__ import annotations

import strawberry

from fb.application.profile.dtos import (
    ProfileOutput,
    UpdateProfileInput as UpdateProfileDTO,
)
from fb.application.profile.update_profile import UpdateProfileUseCase
from fb.domain.shared.entity_id import EntityId
from fb.infrastructure.repositories.profile_repo import SqlAlchemyProfileRepository
from fb.infrastructure.repositories.user_repo import SqlAlchemyUserRepository
from fb.presentation.graphql.context import GraphQLContext
from fb.presentation.graphql.inputs.profile import UpdateProfileInput
from fb.presentation.graphql.types.profile import ProfileType


@strawberry.type
class ProfileMutation:
    @strawberry.mutation
    async def update_profile(
        self, info: strawberry.types.Info, input: UpdateProfileInput
    ) -> ProfileType:
        """Update the authenticated user's profile."""
        ctx: GraphQLContext = info.context
        if not ctx.is_authenticated:
            raise PermissionError("Authentication required")

        container = ctx.container
        uow = container.create_uow()

        async with uow:
            profile_repo = SqlAlchemyProfileRepository(uow.session)
            user_repo = SqlAlchemyUserRepository(uow.session)
            use_case = UpdateProfileUseCase(
                profile_repo=profile_repo,
                user_repo=user_repo,
                uow=uow,
            )
            result = await use_case.execute(
                UpdateProfileDTO(
                    user_id=ctx.current_user_id,  # type: ignore[arg-type]
                    bio=input.bio,
                    location=input.location,
                    website=input.website,
                )
            )

        return _to_type(result)

    @strawberry.mutation
    async def upload_avatar(
        self, info: strawberry.types.Info, avatar_url: str
    ) -> ProfileType:
        """Update the authenticated user's avatar URL."""
        ctx: GraphQLContext = info.context
        if not ctx.is_authenticated:
            raise PermissionError("Authentication required")

        container = ctx.container
        uow = container.create_uow()

        async with uow:
            profile_repo = SqlAlchemyProfileRepository(uow.session)
            user_repo = SqlAlchemyUserRepository(uow.session)
            use_case = UpdateProfileUseCase(
                profile_repo=profile_repo,
                user_repo=user_repo,
                uow=uow,
            )
            # First update profile to ensure it exists, then update avatar
            result = await use_case.execute(
                UpdateProfileDTO(
                    user_id=ctx.current_user_id,  # type: ignore[arg-type]
                )
            )

        # Now update the avatar
        uow2 = container.create_uow()
        async with uow2:
            profile_repo = SqlAlchemyProfileRepository(uow2.session)
            user_repo = SqlAlchemyUserRepository(uow2.session)

            entity_id = EntityId.from_str(ctx.current_user_id)  # type: ignore[arg-type]
            profile = await profile_repo.find_by_user_id(entity_id)
            if profile is not None:
                updated_profile = profile.update_avatar(avatar_url)
                await profile_repo.update(updated_profile)
                await uow2.commit()

                user = await user_repo.find_by_id(entity_id)
                display_name = user.display_name if user else ""

                return ProfileType(
                    id=strawberry.ID(str(updated_profile.id)),
                    user_id=strawberry.ID(str(updated_profile.user_id)),
                    bio=updated_profile.bio,
                    avatar_url=avatar_url,
                    cover_photo_url=updated_profile.cover_photo_url,
                    location=updated_profile.location,
                    website=updated_profile.website,
                    display_name=display_name,
                )

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
