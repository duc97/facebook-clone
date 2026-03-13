from __future__ import annotations

import os
import tempfile

import pytest

from fb.infrastructure.storage.local_storage import LocalFileStorage


class TestLocalFileStorage:
    async def test_upload_creates_file(self, tmp_path: object) -> None:
        """upload() writes file data and returns URL."""
        upload_dir = str(tmp_path)
        storage = LocalFileStorage(upload_dir)

        url = await storage.upload(b"test data", "avatar.png", "image/png")

        assert url == "/uploads/avatar.png"
        import pathlib
        file_path = pathlib.Path(upload_dir) / "avatar.png"
        assert file_path.exists()
        assert file_path.read_bytes() == b"test data"

    async def test_upload_creates_directory(self) -> None:
        """upload() creates upload directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as base:
            upload_dir = os.path.join(base, "new_dir", "uploads")
            storage = LocalFileStorage(upload_dir)

            url = await storage.upload(b"data", "file.jpg", "image/jpeg")

            assert url == "/uploads/file.jpg"
            assert os.path.isdir(upload_dir)

    async def test_delete_removes_file(self, tmp_path: object) -> None:
        """delete() removes file from filesystem."""
        upload_dir = str(tmp_path)
        storage = LocalFileStorage(upload_dir)

        # Create the file first
        await storage.upload(b"to delete", "delete_me.png", "image/png")

        # Delete it
        await storage.delete("/uploads/delete_me.png")

        import pathlib
        assert not (pathlib.Path(upload_dir) / "delete_me.png").exists()

    async def test_delete_nonexistent_file_is_noop(self, tmp_path: object) -> None:
        """delete() does nothing if file doesn't exist."""
        storage = LocalFileStorage(str(tmp_path))
        # Should not raise
        await storage.delete("/uploads/nonexistent.png")

    def test_init_sets_upload_dir(self) -> None:
        """Constructor stores the upload directory."""
        storage = LocalFileStorage("/some/path")
        assert storage._upload_dir == "/some/path"
