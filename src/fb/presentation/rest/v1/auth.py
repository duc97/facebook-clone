from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Request, Response

from fb.application.auth.dtos import (
    EditUserInput as EditUserDTO,
    LoginInput as LoginDTO,
    LogoutInput as LogoutDTO,
    RefreshTokenInput as RefreshDTO,
    RegisterInput as RegisterDTO,
)
from fb.application.auth.edit_user import EditUserUseCase
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
    EditUserRequest,
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    RegisterRequest,
    MessageResponse,
    TokenResponse,
    UserResponse,
)

router = APIRouter(tags=["auth"])


# ── POST /users — Sign up ──────────────────────────────────────────────


@router.post("/users", status_code=201)
async def register(
    body: RegisterRequest,
    container: Container = Depends(get_container),
) -> Response:
    """Sign up a new user and return a token pair."""
    birthday = None
    if body.birthday:
        birthday = date.fromisoformat(body.birthday)

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
                user_name=body.user_name,
                email=body.email,
                first_name=body.first_name,
                last_name=body.last_name,
                password=body.password,
                birthday=birthday,
            )
        )

    return success_response(
        MessageResponse(message="User registered successfully").model_dump(),
        status_code=201,
    )


# ── POST /sessions — Login ─────────────────────────────────────────────


@router.post("/sessions")
async def login(
    body: LoginRequest,
    container: Container = Depends(get_container),
) -> Response:
    """Authenticate a user by username and return a token pair."""
    async with container.session_factory() as session:
        user_repo = SqlAlchemyUserRepository(session)
        use_case = LoginUseCase(
            user_repo=user_repo,
            password_hasher=container.password_hasher,
            token_service=container.token_service,
        )
        result = await use_case.execute(
            LoginDTO(user_name=body.user_name, password=body.password)
        )

    return success_response(
        TokenResponse(
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            token_type=result.token_type,
        ).model_dump(),
    )


# ── PUT /users — Edit profile ──────────────────────────────────────────


@router.put("/users")
async def edit_user(
    body: EditUserRequest,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> Response:
    """Edit the authenticated user's profile fields."""
    birthday = None
    if body.birthday:
        birthday = date.fromisoformat(body.birthday)

    uow = container.create_uow()
    async with uow:
        user_repo = SqlAlchemyUserRepository(uow.session)
        use_case = EditUserUseCase(
            user_repo=user_repo,
            password_hasher=container.password_hasher,
            uow=uow,
        )
        await use_case.execute(
            EditUserDTO(
                user_id=current_user_id,
                first_name=body.first_name,
                last_name=body.last_name,
                birthday=birthday,
                password=body.password,
            )
        )

    return success_response(
        MessageResponse(message="Profile updated successfully").model_dump(),
    )


# ── POST /auth/logout ──────────────────────────────────────────────────


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


# ── POST /auth/refresh ─────────────────────────────────────────────────


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


# ── GET /auth/me ────────────────────────────────────────────────────────


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
            user_name=str(user.user_name),
            email=str(user.email),
            first_name=user.first_name,
            last_name=user.last_name,
            display_name=user.display_name,
            is_active=user.is_active,
        ).model_dump(),
    )
