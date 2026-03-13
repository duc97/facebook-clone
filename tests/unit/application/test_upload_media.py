from __future__ import annotations

import pytest

from fb.domain.shared.entity_id import EntityId
from fb.domain.post.media import InvalidMediaTypeError, MediaTooLargeError
from fb.application.post.upload_media import (
    UploadMediaInput,
    UploadMediaUseCase,
    MediaOutput,
)


class FakeFileStorage:
    """In-memory fake implementing the FileStorage protocol."""

    def __init__(self) -> None:
        self._files: dict[str, bytes] = {}
        self._next_upload_will_fail = False

    async def upload(self, file_data: bytes, filename: str, content_type: str) -> str:
        if self._next_upload_will_fail:
            self._next_upload_will_fail = False
            raise OSError("Storage backend unavailable")
        url = f"https://cdn.example.com/{filename}"
        self._files[url] = file_data
        return url

    async def delete(self, file_url: str) -> None:
        self._files.pop(file_url, None)

    def set_next_upload_will_fail(self) -> None:
        self._next_upload_will_fail = True


class TestUploadMediaUseCase:
    async def test_upload_media_successfully(self) -> None:
        storage = FakeFileStorage()
        use_case = UploadMediaUseCase(file_storage=storage)
        post_id = str(EntityId.generate())

        input_data = UploadMediaInput(
            post_id=post_id,
            file_data=b"fake-image-bytes",
            filename="photo.jpg",
            content_type="image/jpeg",
        )

        result = await use_case.execute(input_data)

        assert isinstance(result, MediaOutput)
        assert result.url.startswith("https://cdn.example.com/")
        assert result.url.endswith(".jpg")
        assert result.content_type == "image/jpeg"
        assert result.file_size == len(b"fake-image-bytes")

    async def test_upload_media_generates_unique_filename(self) -> None:
        storage = FakeFileStorage()
        use_case = UploadMediaUseCase(file_storage=storage)
        post_id = str(EntityId.generate())

        input1 = UploadMediaInput(
            post_id=post_id,
            file_data=b"data1",
            filename="photo.jpg",
            content_type="image/jpeg",
        )
        input2 = UploadMediaInput(
            post_id=post_id,
            file_data=b"data2",
            filename="photo.jpg",
            content_type="image/jpeg",
        )

        result1 = await use_case.execute(input1)
        result2 = await use_case.execute(input2)

        # Both should succeed with different URLs (UUID prefix)
        assert result1.url != result2.url

    async def test_upload_media_invalid_content_type_rejected(self) -> None:
        storage = FakeFileStorage()
        use_case = UploadMediaUseCase(file_storage=storage)
        post_id = str(EntityId.generate())

        input_data = UploadMediaInput(
            post_id=post_id,
            file_data=b"pdf-bytes",
            filename="document.pdf",
            content_type="application/pdf",
        )

        with pytest.raises(InvalidMediaTypeError):
            await use_case.execute(input_data)

    async def test_upload_media_file_too_large_rejected(self) -> None:
        storage = FakeFileStorage()
        use_case = UploadMediaUseCase(file_storage=storage)
        post_id = str(EntityId.generate())
        max_size = 50 * 1024 * 1024

        input_data = UploadMediaInput(
            post_id=post_id,
            file_data=b"x" * (max_size + 1),
            filename="huge.mp4",
            content_type="video/mp4",
        )

        with pytest.raises(MediaTooLargeError):
            await use_case.execute(input_data)

    async def test_upload_failure_propagates_error(self) -> None:
        storage = FakeFileStorage()
        storage.set_next_upload_will_fail()
        use_case = UploadMediaUseCase(file_storage=storage)
        post_id = str(EntityId.generate())

        input_data = UploadMediaInput(
            post_id=post_id,
            file_data=b"some-data",
            filename="photo.jpg",
            content_type="image/jpeg",
        )

        with pytest.raises(OSError, match="Storage backend unavailable"):
            await use_case.execute(input_data)

    async def test_upload_video_successfully(self) -> None:
        storage = FakeFileStorage()
        use_case = UploadMediaUseCase(file_storage=storage)
        post_id = str(EntityId.generate())

        input_data = UploadMediaInput(
            post_id=post_id,
            file_data=b"fake-video-bytes",
            filename="clip.mp4",
            content_type="video/mp4",
        )

        result = await use_case.execute(input_data)

        assert result.content_type == "video/mp4"
        assert result.file_size == len(b"fake-video-bytes")
