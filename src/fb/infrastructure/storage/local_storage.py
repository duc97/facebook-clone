from __future__ import annotations

from pathlib import Path


class LocalFileStorage:
    """Local filesystem implementation of FileStorage protocol."""

    def __init__(self, upload_dir: str) -> None:
        self._upload_dir = upload_dir

    async def upload(self, file_data: bytes, filename: str, content_type: str) -> str:
        """Save file to local filesystem and return relative URL path."""
        upload_path = Path(self._upload_dir)
        upload_path.mkdir(parents=True, exist_ok=True)

        file_path = upload_path / filename
        file_path.write_bytes(file_data)

        return f"/uploads/{filename}"

    async def delete(self, file_url: str) -> None:
        """Delete a file by its URL path."""
        # Extract filename from URL path
        filename = file_url.rsplit("/", 1)[-1]
        file_path = Path(self._upload_dir) / filename
        if file_path.exists():
            file_path.unlink()

    async def generate_presigned_url(self, file_url: str, expires_in: int = 3600) -> str:
        """For local storage, just return the URL as-is."""
        return file_url
