from __future__ import annotations

from unittest.mock import AsyncMock, patch

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
        storage_backend="local",
    )
    return create_app(settings)


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestMediaEndpoints:
    async def test_upload_media_without_auth_returns_401(
        self, client: AsyncClient
    ) -> None:
        """POST /api/v1/posts/{id}/media without Authorization header → 401."""
        fake_post_id = "550e8400-e29b-41d4-a716-446655440000"
        response = await client.post(
            f"/api/v1/posts/{fake_post_id}/media",
            files={"file": ("photo.jpg", b"fake-image-data", "image/jpeg")},
        )
        assert response.status_code == 401

    async def test_upload_media_invalid_content_type_returns_415(
        self, client: AsyncClient, app
    ) -> None:
        """POST /api/v1/posts/{id}/media with invalid content type → 415."""
        container = app.state.container
        token = container.token_service.create_access_token(
            "550e8400-e29b-41d4-a716-446655440000", "test@example.com"
        )

        fake_post_id = "550e8400-e29b-41d4-a716-446655440000"

        # Patch the token blacklist check to avoid needing a live Redis
        with patch.object(
            container.token_blacklist, "is_blacklisted", new_callable=AsyncMock, return_value=False
        ):
            response = await client.post(
                f"/api/v1/posts/{fake_post_id}/media",
                files={"file": ("document.pdf", b"fake-pdf-data", "application/pdf")},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 415

    async def test_delete_media_without_auth_returns_401(
        self, client: AsyncClient
    ) -> None:
        """DELETE /api/v1/posts/{id}/media/{media_id} without auth → 401."""
        fake_post_id = "550e8400-e29b-41d4-a716-446655440000"
        fake_media_id = "660e8400-e29b-41d4-a716-446655440000"
        response = await client.delete(
            f"/api/v1/posts/{fake_post_id}/media/{fake_media_id}",
        )
        assert response.status_code == 401


class TestMediaModuleImports:
    """Verify all media module components can be imported correctly."""

    def test_domain_imports(self) -> None:
        from fb.domain.post.media import (
            MediaAttachment,
            MediaError,
            InvalidMediaTypeError,
            MediaTooLargeError,
        )

        assert MediaAttachment is not None
        assert MediaError is not None
        assert InvalidMediaTypeError is not None
        assert MediaTooLargeError is not None

    def test_application_imports(self) -> None:
        from fb.application.post.upload_media import (
            UploadMediaInput,
            UploadMediaUseCase,
            MediaOutput,
        )

        assert UploadMediaInput is not None
        assert UploadMediaUseCase is not None
        assert MediaOutput is not None

    def test_infrastructure_imports(self) -> None:
        from fb.infrastructure.storage.s3_storage import S3FileStorage

        assert S3FileStorage is not None

    def test_presentation_schema_imports(self) -> None:
        from fb.presentation.rest.v1.schemas import MediaUploadResponse

        assert MediaUploadResponse is not None
