from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from fb.application.auth.dtos import (
    LoginInput,
    LogoutInput,
    RefreshTokenInput,
    RegisterInput,
    TokenOutput,
)
from fb.application.auth.login import LoginUseCase
from fb.application.auth.logout import LogoutUseCase
from fb.application.auth.refresh_token import RefreshTokenUseCase
from fb.application.auth.register import RegisterUseCase
from fb.domain.auth.entities import User
from fb.domain.auth.exceptions import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenBlacklistedError,
    UserInactiveError,
    UserNotFoundError,
)
from fb.domain.auth.value_objects import Email, HashedPassword
from fb.domain.shared.entity_id import EntityId


# ─── Mocks ──────────────────────────────────────────────


class FakeUserRepo:
    def __init__(self, users: dict[str, User] | None = None) -> None:
        self._users: dict[str, User] = users or {}

    async def find_by_id(self, user_id: EntityId) -> User | None:
        return self._users.get(str(user_id))

    async def find_by_email(self, email: str) -> User | None:
        for user in self._users.values():
            if str(user.email) == email:
                return user
        return None

    async def save(self, user: User) -> User:
        self._users[str(user.id)] = user
        return user

    async def update(self, user: User) -> User:
        self._users[str(user.id)] = user
        return user

    async def exists_by_email(self, email: str) -> bool:
        return any(str(u.email) == email for u in self._users.values())


class FakePasswordHasher:
    def hash(self, password: str) -> str:
        return f"hashed_{password}"

    def verify(self, password: str, hashed: str) -> bool:
        return hashed == f"hashed_{password}"


class FakeTokenService:
    def create_access_token(self, user_id: str, email: str) -> str:
        return f"access_{user_id}"

    def create_refresh_token(self, user_id: str) -> str:
        return f"refresh_{user_id}"

    def decode_access_token(self, token: str) -> dict[str, str]:
        if not token.startswith("access_"):
            raise ValueError("Invalid access token")
        user_id = token.replace("access_", "")
        return {"sub": user_id, "email": "test@example.com"}

    def decode_refresh_token(self, token: str) -> dict[str, str]:
        if not token.startswith("refresh_"):
            raise ValueError("Invalid refresh token")
        user_id = token.replace("refresh_", "")
        return {"sub": user_id}


class FakeTokenBlacklist:
    def __init__(self) -> None:
        self._blacklisted: set[str] = set()

    async def blacklist(self, token: str, expires_in: int) -> None:
        self._blacklisted.add(token)

    async def is_blacklisted(self, token: str) -> bool:
        return token in self._blacklisted


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> FakeUnitOfWork:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        if exc_type is not None:
            self.rolled_back = True

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


# ─── Fixtures ──────────────────────────────────────────────


@pytest.fixture
def user_repo() -> FakeUserRepo:
    return FakeUserRepo()


@pytest.fixture
def password_hasher() -> FakePasswordHasher:
    return FakePasswordHasher()


@pytest.fixture
def token_service() -> FakeTokenService:
    return FakeTokenService()


@pytest.fixture
def token_blacklist() -> FakeTokenBlacklist:
    return FakeTokenBlacklist()


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


def _make_user(
    user_id: str | None = None,
    email: str = "test@example.com",
    password: str = "hashed_password123",
    name: str = "Test User",
    is_active: bool = True,
) -> User:
    eid = EntityId.from_str(user_id) if user_id else EntityId.generate()
    return User(
        id=eid,
        email=Email(email),
        hashed_password=HashedPassword(password),
        display_name=name,
        is_active=is_active,
    )


# ─── Register Tests ──────────────────────────────────────


class TestRegisterUseCase:
    async def test_register_success(
        self,
        user_repo: FakeUserRepo,
        password_hasher: FakePasswordHasher,
        token_service: FakeTokenService,
        uow: FakeUnitOfWork,
    ) -> None:
        use_case = RegisterUseCase(user_repo, password_hasher, token_service, uow)
        result = await use_case.execute(
            RegisterInput(
                email="new@example.com",
                password="password123",
                display_name="New User",
            )
        )
        assert isinstance(result, TokenOutput)
        assert result.access_token.startswith("access_")
        assert result.refresh_token.startswith("refresh_")
        assert result.token_type == "bearer"
        assert uow.committed is True

    async def test_register_duplicate_email_raises(
        self,
        user_repo: FakeUserRepo,
        password_hasher: FakePasswordHasher,
        token_service: FakeTokenService,
        uow: FakeUnitOfWork,
    ) -> None:
        existing = _make_user(email="taken@example.com")
        user_repo._users[str(existing.id)] = existing

        use_case = RegisterUseCase(user_repo, password_hasher, token_service, uow)
        with pytest.raises(EmailAlreadyExistsError):
            await use_case.execute(
                RegisterInput(
                    email="taken@example.com",
                    password="pass",
                    display_name="Dup",
                )
            )

    async def test_register_creates_user_in_repo(
        self,
        user_repo: FakeUserRepo,
        password_hasher: FakePasswordHasher,
        token_service: FakeTokenService,
        uow: FakeUnitOfWork,
    ) -> None:
        use_case = RegisterUseCase(user_repo, password_hasher, token_service, uow)
        await use_case.execute(
            RegisterInput(
                email="new@example.com",
                password="password123",
                display_name="New User",
            )
        )
        assert len(user_repo._users) == 1
        saved_user = list(user_repo._users.values())[0]
        assert str(saved_user.email) == "new@example.com"
        assert saved_user.hashed_password.value == "hashed_password123"


# ─── Login Tests ──────────────────────────────────────────


class TestLoginUseCase:
    async def test_login_success(
        self,
        user_repo: FakeUserRepo,
        password_hasher: FakePasswordHasher,
        token_service: FakeTokenService,
    ) -> None:
        user = _make_user(email="user@example.com", password="hashed_mypassword")
        user_repo._users[str(user.id)] = user

        use_case = LoginUseCase(user_repo, password_hasher, token_service)
        result = await use_case.execute(
            LoginInput(email="user@example.com", password="mypassword")
        )
        assert isinstance(result, TokenOutput)
        assert result.access_token.startswith("access_")
        assert result.refresh_token.startswith("refresh_")

    async def test_login_user_not_found(
        self,
        user_repo: FakeUserRepo,
        password_hasher: FakePasswordHasher,
        token_service: FakeTokenService,
    ) -> None:
        use_case = LoginUseCase(user_repo, password_hasher, token_service)
        with pytest.raises(InvalidCredentialsError):
            await use_case.execute(
                LoginInput(email="nope@example.com", password="pass")
            )

    async def test_login_wrong_password(
        self,
        user_repo: FakeUserRepo,
        password_hasher: FakePasswordHasher,
        token_service: FakeTokenService,
    ) -> None:
        user = _make_user(email="user@example.com", password="hashed_correct")
        user_repo._users[str(user.id)] = user

        use_case = LoginUseCase(user_repo, password_hasher, token_service)
        with pytest.raises(InvalidCredentialsError):
            await use_case.execute(
                LoginInput(email="user@example.com", password="wrong")
            )

    async def test_login_inactive_user(
        self,
        user_repo: FakeUserRepo,
        password_hasher: FakePasswordHasher,
        token_service: FakeTokenService,
    ) -> None:
        user = _make_user(
            email="inactive@example.com",
            password="hashed_pass",
            is_active=False,
        )
        user_repo._users[str(user.id)] = user

        use_case = LoginUseCase(user_repo, password_hasher, token_service)
        with pytest.raises(UserInactiveError):
            await use_case.execute(
                LoginInput(email="inactive@example.com", password="pass")
            )


# ─── Logout Tests ──────────────────────────────────────────


class TestLogoutUseCase:
    async def test_logout_blacklists_tokens(
        self, token_blacklist: FakeTokenBlacklist
    ) -> None:
        use_case = LogoutUseCase(token_blacklist)
        await use_case.execute(
            LogoutInput(access_token="acc_token", refresh_token="ref_token")
        )
        assert await token_blacklist.is_blacklisted("acc_token")
        assert await token_blacklist.is_blacklisted("ref_token")


# ─── Refresh Token Tests ──────────────────────────────────


class TestRefreshTokenUseCase:
    async def test_refresh_success(
        self,
        user_repo: FakeUserRepo,
        token_service: FakeTokenService,
        token_blacklist: FakeTokenBlacklist,
    ) -> None:
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        user = _make_user(user_id=user_id, email="user@example.com")
        user_repo._users[user_id] = user

        use_case = RefreshTokenUseCase(token_service, token_blacklist, user_repo)
        result = await use_case.execute(
            RefreshTokenInput(refresh_token=f"refresh_{user_id}")
        )
        assert isinstance(result, TokenOutput)
        assert result.access_token.startswith("access_")

    async def test_refresh_blacklisted_token(
        self,
        user_repo: FakeUserRepo,
        token_service: FakeTokenService,
        token_blacklist: FakeTokenBlacklist,
    ) -> None:
        await token_blacklist.blacklist("refresh_bad", 3600)

        use_case = RefreshTokenUseCase(token_service, token_blacklist, user_repo)
        with pytest.raises(TokenBlacklistedError):
            await use_case.execute(
                RefreshTokenInput(refresh_token="refresh_bad")
            )

    async def test_refresh_invalid_token(
        self,
        user_repo: FakeUserRepo,
        token_service: FakeTokenService,
        token_blacklist: FakeTokenBlacklist,
    ) -> None:
        use_case = RefreshTokenUseCase(token_service, token_blacklist, user_repo)
        with pytest.raises(InvalidTokenError):
            await use_case.execute(
                RefreshTokenInput(refresh_token="invalid_token")
            )

    async def test_refresh_user_not_found(
        self,
        user_repo: FakeUserRepo,
        token_service: FakeTokenService,
        token_blacklist: FakeTokenBlacklist,
    ) -> None:
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        # User does NOT exist in repo

        use_case = RefreshTokenUseCase(token_service, token_blacklist, user_repo)
        with pytest.raises(UserNotFoundError):
            await use_case.execute(
                RefreshTokenInput(refresh_token=f"refresh_{user_id}")
            )

    async def test_refresh_inactive_user(
        self,
        user_repo: FakeUserRepo,
        token_service: FakeTokenService,
        token_blacklist: FakeTokenBlacklist,
    ) -> None:
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        user = _make_user(user_id=user_id, is_active=False)
        user_repo._users[user_id] = user

        use_case = RefreshTokenUseCase(token_service, token_blacklist, user_repo)
        with pytest.raises(InvalidTokenError, match="deactivated"):
            await use_case.execute(
                RefreshTokenInput(refresh_token=f"refresh_{user_id}")
            )
