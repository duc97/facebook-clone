from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from typing import Any

import aioboto3


class S3FileStorage:
    """S3-compatible file storage implementing the FileStorage protocol.

    Supports AWS S3, MinIO, and LocalStack via configurable endpoint_url.
    """

    def __init__(
        self,
        bucket_name: str,
        region: str = "us-east-1",
        endpoint_url: str = "",
    ) -> None:
        self._bucket_name = bucket_name
        self._region = region
        self._endpoint_url = endpoint_url

    @asynccontextmanager
    async def _get_client(self) -> AsyncGenerator[Any, None]:
        session = aioboto3.Session()
        kwargs: dict[str, Any] = {
            "service_name": "s3",
            "region_name": self._region,
        }
        if self._endpoint_url:
            kwargs["endpoint_url"] = self._endpoint_url
        async with session.client(**kwargs) as client:
            yield client

    async def upload(self, file_data: bytes, filename: str, content_type: str) -> str:
        """Upload file to S3 and return its public URL."""
        extension = _extract_extension(filename)
        key = f"{uuid.uuid4()}{extension}"

        async with self._get_client() as client:
            await client.put_object(
                Bucket=self._bucket_name,
                Key=key,
                Body=file_data,
                ContentType=content_type,
            )

        return self._build_url(key)

    async def delete(self, file_url: str) -> None:
        """Delete a file from S3 by its URL."""
        key = _extract_key_from_url(file_url)

        async with self._get_client() as client:
            await client.delete_object(
                Bucket=self._bucket_name,
                Key=key,
            )

    async def generate_presigned_url(self, file_url: str, expires_in: int = 3600) -> str:
        """Generate a presigned URL for private S3 objects.

        Args:
            file_url: The full S3 URL (or just the key)
            expires_in: Expiry in seconds (default 1 hour)

        Returns:
            Presigned URL valid for `expires_in` seconds.
        """
        key = _extract_key_from_url(file_url)
        async with self._get_client() as client:
            url: str = await client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket_name, "Key": key},
                ExpiresIn=expires_in,
            )
        return url

    def _build_url(self, key: str) -> str:
        """Build the public URL for an object key."""
        if self._endpoint_url:
            return f"{self._endpoint_url}/{self._bucket_name}/{key}"
        return f"https://{self._bucket_name}.s3.{self._region}.amazonaws.com/{key}"


def _extract_extension(filename: str) -> str:
    """Return the file extension including the dot, or empty string."""
    dot_index = filename.rfind(".")
    if dot_index == -1:
        return ""
    return filename[dot_index:]


def _extract_key_from_url(url: str) -> str:
    """Extract the S3 object key from its URL (last path component)."""
    return url.rsplit("/", 1)[-1]
