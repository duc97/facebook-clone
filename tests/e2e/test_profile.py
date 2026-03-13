from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from fb.config import Settings
from fb.main import create_app


@pytest.fixture
def app():
    settings = Settings(
        database_url="postgresql+asyncpg://fb:fb_password@localhost:5432/facebook_clone_test",
        redis_url="redis://localhost:6379/1",
        jwt_secret_key="test-secret-key-for-e2e-testing",
        debug=True,
    )
    return create_app(settings)


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestProfileGraphQL:
    async def test_get_profile_unauthenticated(self, client: AsyncClient) -> None:
        """Querying a profile without auth returns null or error."""
        query = {
            "query": """
                query GetProfile($userId: ID!) {
                    profile(userId: $userId) {
                        id
                        bio
                        displayName
                    }
                }
            """,
            "variables": {"userId": "550e8400-e29b-41d4-a716-446655440000"},
        }
        response = await client.post("/api/v1/graphql", json=query)
        assert response.status_code == 200
        data = response.json()
        has_errors = data.get("errors") is not None
        has_null_profile = (
            data.get("data") is not None and data["data"].get("profile") is None
        )
        assert has_errors or has_null_profile

    async def test_update_profile_unauthenticated(self, client: AsyncClient) -> None:
        """Updating profile without auth returns 401."""
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        response = await client.put(
            f"/api/v1/users/{user_id}/profile",
            json={"bio": "New bio"},
        )
        assert response.status_code == 401


class TestProfileModuleImports:
    """Verify all profile module components can be imported correctly."""

    def test_domain_entities_import(self) -> None:
        from fb.domain.profile.entities import Profile
        from fb.domain.profile.exceptions import (
            InvalidFileTypeError,
            ProfileAlreadyExistsError,
            ProfileError,
            ProfileNotFoundError,
        )
        from fb.domain.profile.repository import ProfileRepository
        from fb.domain.profile.services import FileStorage

        assert Profile is not None
        assert ProfileRepository is not None
        assert FileStorage is not None

    def test_application_import(self) -> None:
        from fb.application.profile.dtos import (
            ProfileOutput,
            UpdateProfileInput,
            UploadAvatarInput,
        )
        from fb.application.profile.get_profile import GetProfileUseCase
        from fb.application.profile.update_profile import UpdateProfileUseCase
        from fb.application.profile.upload_avatar import UploadAvatarUseCase

        assert GetProfileUseCase is not None
        assert UpdateProfileUseCase is not None
        assert UploadAvatarUseCase is not None

    def test_infrastructure_import(self) -> None:
        from fb.infrastructure.database.models.profile import ProfileModel
        from fb.infrastructure.repositories.profile_repo import SqlAlchemyProfileRepository
        from fb.infrastructure.storage.local_storage import LocalFileStorage

        assert ProfileModel is not None
        assert SqlAlchemyProfileRepository is not None
        assert LocalFileStorage is not None

    def test_presentation_import(self) -> None:
        from fb.presentation.graphql.types.profile import ProfileType
        from fb.presentation.graphql.inputs.profile import UpdateProfileInput
        from fb.presentation.graphql.queries.profile import ProfileQuery
        from fb.presentation.graphql.mutations.profile import ProfileMutation

        assert ProfileType is not None
        assert UpdateProfileInput is not None
        assert ProfileQuery is not None
        assert ProfileMutation is not None
