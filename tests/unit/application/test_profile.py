from __future__ import annotations

from typing import Any

import pytest

from fb.application.profile.dtos import (
    ProfileOutput,
    UpdateProfileInput,
    UploadAvatarInput,
)
from fb.application.profile.get_profile import GetProfileUseCase
from fb.application.profile.update_profile import UpdateProfileUseCase
from fb.application.profile.upload_avatar import UploadAvatarUseCase
from fb.domain.auth.entities import User
from fb.domain.auth.value_objects import Email, HashedPassword
from fb.domain.profile.entities import Profile
from fb.domain.profile.exceptions import (
    InvalidFileTypeError,
)
from fb.domain.shared.entity_id import EntityId


# ─── Fakes ──────────────────────────────────────────────


class FakeProfileRepo:
    def __init__(self, profiles: dict[str, Profile] | None = None) -> None:
        self._profiles: dict[str, Profile] = profiles or {}

    async def find_by_user_id(self, user_id: EntityId) -> Profile | None:
        return self._profiles.get(str(user_id))

    async def save(self, profile: Profile) -> Profile:
        self._profiles[str(profile.user_id)] = profile
        return profile

    async def update(self, profile: Profile) -> Profile:
        self._profiles[str(profile.user_id)] = profile
        return profile

    async def exists_by_user_id(self, user_id: EntityId) -> bool:
        return str(user_id) in self._profiles


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


class FakeFileStorage:
    def __init__(self) -> None:
        self.uploaded_files: list[tuple[str, str]] = []  # (filename, content_type)

    async def upload(self, file_data: bytes, filename: str, content_type: str) -> str:
        self.uploaded_files.append((filename, content_type))
        return f"/uploads/{filename}"

    async def delete(self, file_url: str) -> None:
        pass


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


# ─── Helpers ──────────────────────────────────────────────


def _make_user(
    user_id: str | None = None,
    email: str = "test@example.com",
    name: str = "Test User",
) -> User:
    eid = EntityId.from_str(user_id) if user_id else EntityId.generate()
    return User(
        id=eid,
        email=Email(email),
        hashed_password=HashedPassword("hashed_pw"),
        display_name=name,
    )


def _make_profile(
    user_id: EntityId | None = None,
    bio: str = "Hello",
) -> Profile:
    uid = user_id or EntityId.generate()
    return Profile.create(user_id=uid, bio=bio)


# ─── Fixtures ──────────────────────────────────────────────


@pytest.fixture
def profile_repo() -> FakeProfileRepo:
    return FakeProfileRepo()


@pytest.fixture
def user_repo() -> FakeUserRepo:
    return FakeUserRepo()


@pytest.fixture
def file_storage() -> FakeFileStorage:
    return FakeFileStorage()


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


# ─── GetProfileUseCase Tests ──────────────────────────────


class TestGetProfileUseCase:
    async def test_get_profile_success(
        self,
        profile_repo: FakeProfileRepo,
        user_repo: FakeUserRepo,
    ) -> None:
        user = _make_user(name="John Doe")
        user_repo._users[str(user.id)] = user

        profile = _make_profile(user_id=user.id, bio="My bio")
        profile_repo._profiles[str(user.id)] = profile

        use_case = GetProfileUseCase(
            profile_repo=profile_repo,
            user_repo=user_repo,
        )
        result = await use_case.execute(str(user.id))

        assert isinstance(result, ProfileOutput)
        assert result.user_id == str(user.id)
        assert result.bio == "My bio"
        assert result.display_name == "John Doe"

    async def test_get_profile_not_found(
        self,
        profile_repo: FakeProfileRepo,
        user_repo: FakeUserRepo,
    ) -> None:
        user = _make_user()
        user_repo._users[str(user.id)] = user

        use_case = GetProfileUseCase(
            profile_repo=profile_repo,
            user_repo=user_repo,
        )
        result = await use_case.execute(str(user.id))
        assert result is None


# ─── UpdateProfileUseCase Tests ──────────────────────────────


class TestUpdateProfileUseCase:
    async def test_update_profile_success(
        self,
        profile_repo: FakeProfileRepo,
        user_repo: FakeUserRepo,
        uow: FakeUnitOfWork,
    ) -> None:
        user = _make_user(name="Jane Doe")
        user_repo._users[str(user.id)] = user

        profile = _make_profile(user_id=user.id, bio="Old bio")
        profile_repo._profiles[str(user.id)] = profile

        use_case = UpdateProfileUseCase(
            profile_repo=profile_repo,
            user_repo=user_repo,
            uow=uow,
        )
        result = await use_case.execute(
            UpdateProfileInput(
                user_id=str(user.id),
                bio="New bio",
                location="NYC",
            )
        )

        assert isinstance(result, ProfileOutput)
        assert result.bio == "New bio"
        assert result.location == "NYC"
        assert result.display_name == "Jane Doe"
        assert uow.committed is True

    async def test_update_profile_creates_if_not_exists(
        self,
        profile_repo: FakeProfileRepo,
        user_repo: FakeUserRepo,
        uow: FakeUnitOfWork,
    ) -> None:
        user = _make_user(name="New User")
        user_repo._users[str(user.id)] = user

        use_case = UpdateProfileUseCase(
            profile_repo=profile_repo,
            user_repo=user_repo,
            uow=uow,
        )
        result = await use_case.execute(
            UpdateProfileInput(
                user_id=str(user.id),
                bio="First bio",
            )
        )

        assert isinstance(result, ProfileOutput)
        assert result.bio == "First bio"
        assert result.display_name == "New User"
        assert uow.committed is True
        # Verify profile was saved in repo
        assert str(user.id) in profile_repo._profiles


# ─── UploadAvatarUseCase Tests ──────────────────────────────


class TestUploadAvatarUseCase:
    async def test_upload_avatar_success(
        self,
        profile_repo: FakeProfileRepo,
        user_repo: FakeUserRepo,
        file_storage: FakeFileStorage,
        uow: FakeUnitOfWork,
    ) -> None:
        user = _make_user(name="Avatar User")
        user_repo._users[str(user.id)] = user

        profile = _make_profile(user_id=user.id)
        profile_repo._profiles[str(user.id)] = profile

        use_case = UploadAvatarUseCase(
            profile_repo=profile_repo,
            user_repo=user_repo,
            file_storage=file_storage,
            uow=uow,
        )
        result = await use_case.execute(
            UploadAvatarInput(
                user_id=str(user.id),
                file_data=b"fake image bytes",
                filename="avatar.jpg",
                content_type="image/jpeg",
            )
        )

        assert isinstance(result, ProfileOutput)
        assert result.avatar_url == "/uploads/avatar.jpg"
        assert result.display_name == "Avatar User"
        assert uow.committed is True
        assert len(file_storage.uploaded_files) == 1

    async def test_upload_avatar_invalid_type(
        self,
        profile_repo: FakeProfileRepo,
        user_repo: FakeUserRepo,
        file_storage: FakeFileStorage,
        uow: FakeUnitOfWork,
    ) -> None:
        user = _make_user()
        user_repo._users[str(user.id)] = user

        profile = _make_profile(user_id=user.id)
        profile_repo._profiles[str(user.id)] = profile

        use_case = UploadAvatarUseCase(
            profile_repo=profile_repo,
            user_repo=user_repo,
            file_storage=file_storage,
            uow=uow,
        )

        with pytest.raises(InvalidFileTypeError):
            await use_case.execute(
                UploadAvatarInput(
                    user_id=str(user.id),
                    file_data=b"pdf content",
                    filename="document.pdf",
                    content_type="application/pdf",
                )
            )
        # Verify file was NOT uploaded
        assert len(file_storage.uploaded_files) == 0
