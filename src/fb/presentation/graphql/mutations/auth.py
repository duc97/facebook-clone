from __future__ import annotations

from typing import Any

import strawberry

from fb.application.auth.dtos import (
    LoginInput as LoginDTO,
    LogoutInput as LogoutDTO,
    RefreshTokenInput as RefreshDTO,
    RegisterInput as RegisterDTO,
)
from fb.application.auth.login import LoginUseCase
from fb.application.auth.logout import LogoutUseCase
from fb.application.auth.refresh_token import RefreshTokenUseCase
from fb.application.auth.register import RegisterUseCase
from fb.domain.auth.exceptions import (
    AuthError,
    EmailAlreadyExistsError,
    InvalidCredentialsError,
)
from fb.infrastructure.repositories.user_repo import SqlAlchemyUserRepository
from fb.presentation.graphql.context import GraphQLContext
from fb.presentation.graphql.inputs.auth import (
    LoginInput,
    RefreshTokenInput,
    RegisterInput,
)
from fb.presentation.graphql.types.auth import MessageResponse, TokenResponse


@strawberry.type
class AuthMutation:
    @strawberry.mutation
    async def register(self, info: strawberry.types.Info, input: RegisterInput) -> TokenResponse:
        ctx: GraphQLContext = info.context
        container = ctx.container

        uow = container.create_uow()
        async with uow:
            user_repo = SqlAlchemyUserRepository(uow.session)
            use_case = RegisterUseCase(
                user_repo=user_repo,
                password_hasher=container.password_hasher,
                token_service=container.token_service,
                uow=uow,
            )

            result = await use_case.execute(
                RegisterDTO(
                    email=input.email,
                    password=input.password,
                    display_name=input.display_name,
                )
            )

        return TokenResponse(
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            token_type=result.token_type,
        )

    @strawberry.mutation
    async def login(self, info: strawberry.types.Info, input: LoginInput) -> TokenResponse:
        ctx: GraphQLContext = info.context
        container = ctx.container

        async with container.session_factory() as session:
            user_repo = SqlAlchemyUserRepository(session)
            use_case = LoginUseCase(
                user_repo=user_repo,
                password_hasher=container.password_hasher,
                token_service=container.token_service,
            )

            result = await use_case.execute(
                LoginDTO(email=input.email, password=input.password)
            )

        return TokenResponse(
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            token_type=result.token_type,
        )

    @strawberry.mutation
    async def logout(self, info: strawberry.types.Info) -> MessageResponse:
        ctx: GraphQLContext = info.context
        if not ctx.is_authenticated:
            return MessageResponse(message="Not authenticated", success=False)

        # Get tokens from headers
        request = ctx.req
        auth_header = request.headers.get("authorization", "")
        access_token = auth_header.replace("Bearer ", "") if auth_header else ""
        refresh_token = request.headers.get("x-refresh-token", "")

        if not access_token:
            return MessageResponse(message="No token provided", success=False)

        use_case = LogoutUseCase(ctx.container.token_blacklist)
        await use_case.execute(
            LogoutDTO(access_token=access_token, refresh_token=refresh_token)
        )

        return MessageResponse(message="Logged out successfully", success=True)

    @strawberry.mutation
    async def refresh_token(
        self, info: strawberry.types.Info, input: RefreshTokenInput
    ) -> TokenResponse:
        ctx: GraphQLContext = info.context
        container = ctx.container

        async with container.session_factory() as session:
            user_repo = SqlAlchemyUserRepository(session)
            use_case = RefreshTokenUseCase(
                token_service=container.token_service,
                token_blacklist=container.token_blacklist,
                user_repo=user_repo,
            )

            result = await use_case.execute(
                RefreshDTO(refresh_token=input.refresh_token)
            )

        return TokenResponse(
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            token_type=result.token_type,
        )
