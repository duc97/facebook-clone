from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

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
from fb.container import Container
from fb.domain.shared.entity_id import EntityId
from fb.infrastructure.repositories.user_repo import SqlAlchemyUserRepository
from fb.presentation.dependencies import get_container, get_current_user_id
from fb.presentation.rest.response import success_response
from fb.presentation.rest.v1.schemas import (
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(tags=["auth"])


@router.post("/auth/register", status_code=201)
async def register(
    body: RegisterRequest,
    container: Container = Depends(get_container),
) -> Response:
    """Register a new user and return a token pair."""
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
                email=body.email,
                password=body.password,
                display_name=body.display_name,
            )
        )

    return success_response(
        TokenResponse(
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            token_type=result.token_type,
        ).model_dump(),
        status_code=201,
    )


@router.post("/auth/login")
async def login(
    body: LoginRequest,
    container: Container = Depends(get_container),
) -> Response:
    """Authenticate a user and return a token pair."""
    async with container.session_factory() as session:
        user_repo = SqlAlchemyUserRepository(session)
        use_case = LoginUseCase(
            user_repo=user_repo,
            password_hasher=container.password_hasher,
            token_service=container.token_service,
        )
        result = await use_case.execute(
            LoginDTO(email=body.email, password=body.password)
        )

    return success_response(
        TokenResponse(
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            token_type=result.token_type,
        ).model_dump(),
    )


@router.post("/auth/logout", status_code=204)
async def logout(
    request: Request,
    body: LogoutRequest,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> Response:
    """Blacklist the current access and refresh tokens."""
    auth_header = request.headers.get("authorization", "")
    access_token = auth_header.removeprefix("Bearer ")

    use_case = LogoutUseCase(container.token_blacklist)
    await use_case.execute(
        LogoutDTO(
            access_token=access_token,
            refresh_token=body.refresh_token,
        )
    )

    return Response(status_code=204)


@router.post("/auth/refresh")
async def refresh(
    body: RefreshTokenRequest,
    container: Container = Depends(get_container),
) -> Response:
    """Exchange a valid refresh token for a new token pair."""
    async with container.session_factory() as session:
        user_repo = SqlAlchemyUserRepository(session)
        use_case = RefreshTokenUseCase(
            token_service=container.token_service,
            token_blacklist=container.token_blacklist,
            user_repo=user_repo,
        )
        result = await use_case.execute(
            RefreshDTO(refresh_token=body.refresh_token)
        )

    return success_response(
        TokenResponse(
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            token_type=result.token_type,
        ).model_dump(),
    )


@router.get("/auth/me")
async def me(
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> Response:
    """Return the authenticated user's basic information."""
    async with container.session_factory() as session:
        user_repo = SqlAlchemyUserRepository(session)
        user = await user_repo.find_by_id(EntityId.from_str(current_user_id))

    if user is None:
        return Response(status_code=404)

    return success_response(
        UserResponse(
            id=str(user.id),
            email=str(user.email),
            display_name=user.display_name,
            is_active=user.is_active,
        ).model_dump(),
    )
