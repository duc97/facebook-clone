from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class FileStorage(Protocol):
    """Protocol for file storage operations."""

    async def upload(self, file_data: bytes, filename: str, content_type: str) -> str:
        """Upload a file and return its URL."""
        ...

    async def delete(self, file_url: str) -> None:
        """Delete a file by its URL."""
        ...

    async def generate_presigned_url(self, file_url: str, expires_in: int = 3600) -> str:
        """Generate a time-limited access URL for private storage."""
        ...
