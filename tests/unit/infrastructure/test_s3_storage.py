from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fb.domain.profile.services import FileStorage
from fb.infrastructure.storage.s3_storage import S3FileStorage


class TestS3FileStorage:
    def test_implements_file_storage_protocol(self) -> None:
        """S3FileStorage is a structural subtype of FileStorage."""
        storage = S3FileStorage(
            bucket_name="test-bucket",
            region="us-east-1",
        )
        assert isinstance(storage, FileStorage)

    def test_init_stores_configuration(self) -> None:
        storage = S3FileStorage(
            bucket_name="my-bucket",
            region="eu-west-1",
            endpoint_url="http://localhost:4566",
        )
        assert storage._bucket_name == "my-bucket"
        assert storage._region == "eu-west-1"
        assert storage._endpoint_url == "http://localhost:4566"

    def test_init_default_endpoint_url_is_empty(self) -> None:
        storage = S3FileStorage(
            bucket_name="my-bucket",
            region="us-east-1",
        )
        assert storage._endpoint_url == ""

    async def test_upload_generates_unique_filename(self) -> None:
        """Each upload call should produce a unique key (UUID prefix)."""
        storage = S3FileStorage(
            bucket_name="test-bucket",
            region="us-east-1",
        )

        mock_client = AsyncMock()
        mock_client.put_object = AsyncMock()

        with patch.object(storage, "_get_client") as mock_get_client:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_get_client.return_value = mock_ctx

            url1 = await storage.upload(b"data1", "photo.jpg", "image/jpeg")
            url2 = await storage.upload(b"data2", "photo.jpg", "image/jpeg")

        assert url1 != url2
        assert url1.endswith(".jpg")
        assert url2.endswith(".jpg")

    async def test_upload_returns_s3_url(self) -> None:
        storage = S3FileStorage(
            bucket_name="test-bucket",
            region="us-east-1",
        )

        mock_client = AsyncMock()
        mock_client.put_object = AsyncMock()

        with patch.object(storage, "_get_client") as mock_get_client:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_get_client.return_value = mock_ctx

            url = await storage.upload(b"data", "photo.jpg", "image/jpeg")

        assert "test-bucket" in url
        assert url.endswith(".jpg")

    async def test_upload_calls_put_object(self) -> None:
        storage = S3FileStorage(
            bucket_name="test-bucket",
            region="us-east-1",
        )

        mock_client = AsyncMock()
        mock_client.put_object = AsyncMock()

        with patch.object(storage, "_get_client") as mock_get_client:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_get_client.return_value = mock_ctx

            await storage.upload(b"test-data", "photo.jpg", "image/jpeg")

        mock_client.put_object.assert_called_once()
        call_kwargs = mock_client.put_object.call_args
        assert call_kwargs.kwargs["Bucket"] == "test-bucket"
        assert call_kwargs.kwargs["Body"] == b"test-data"
        assert call_kwargs.kwargs["ContentType"] == "image/jpeg"

    async def test_delete_calls_delete_object(self) -> None:
        storage = S3FileStorage(
            bucket_name="test-bucket",
            region="us-east-1",
        )

        mock_client = AsyncMock()
        mock_client.delete_object = AsyncMock()

        with patch.object(storage, "_get_client") as mock_get_client:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_get_client.return_value = mock_ctx

            await storage.delete(
                "https://test-bucket.s3.us-east-1.amazonaws.com/abc123.jpg"
            )

        mock_client.delete_object.assert_called_once()
        call_kwargs = mock_client.delete_object.call_args
        assert call_kwargs.kwargs["Bucket"] == "test-bucket"
        assert call_kwargs.kwargs["Key"] == "abc123.jpg"

    async def test_upload_with_custom_endpoint(self) -> None:
        """When endpoint_url is set (MinIO/LocalStack), URL uses it."""
        storage = S3FileStorage(
            bucket_name="test-bucket",
            region="us-east-1",
            endpoint_url="http://localhost:4566",
        )

        mock_client = AsyncMock()
        mock_client.put_object = AsyncMock()

        with patch.object(storage, "_get_client") as mock_get_client:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_get_client.return_value = mock_ctx

            url = await storage.upload(b"data", "image.png", "image/png")

        assert "localhost:4566" in url
        assert url.endswith(".png")
