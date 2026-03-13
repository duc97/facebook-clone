from __future__ import annotations

import pytest
from datetime import datetime

from fb.domain.shared.entity_id import EntityId
from fb.domain.post.media import (
    MediaAttachment,
    MediaError,
    InvalidMediaTypeError,
    MediaTooLargeError,
)


class TestMediaAttachment:
    def test_create_with_valid_image_jpeg(self) -> None:
        post_id = EntityId.generate()
        attachment = MediaAttachment.create(
            post_id=post_id,
            url="https://cdn.example.com/image.jpg",
            content_type="image/jpeg",
            file_size=1024,
        )

        assert attachment.id is not None
        assert attachment.post_id == post_id
        assert attachment.url == "https://cdn.example.com/image.jpg"
        assert attachment.content_type == "image/jpeg"
        assert attachment.file_size == 1024
        assert attachment.created_at is None

    def test_create_with_valid_image_png(self) -> None:
        post_id = EntityId.generate()
        attachment = MediaAttachment.create(
            post_id=post_id,
            url="https://cdn.example.com/image.png",
            content_type="image/png",
            file_size=2048,
        )
        assert attachment.content_type == "image/png"

    def test_create_with_valid_image_gif(self) -> None:
        post_id = EntityId.generate()
        attachment = MediaAttachment.create(
            post_id=post_id,
            url="https://cdn.example.com/anim.gif",
            content_type="image/gif",
            file_size=500_000,
        )
        assert attachment.content_type == "image/gif"

    def test_create_with_valid_image_webp(self) -> None:
        post_id = EntityId.generate()
        attachment = MediaAttachment.create(
            post_id=post_id,
            url="https://cdn.example.com/photo.webp",
            content_type="image/webp",
            file_size=3072,
        )
        assert attachment.content_type == "image/webp"

    def test_create_with_valid_video_mp4(self) -> None:
        post_id = EntityId.generate()
        attachment = MediaAttachment.create(
            post_id=post_id,
            url="https://cdn.example.com/video.mp4",
            content_type="video/mp4",
            file_size=10_000_000,
        )
        assert attachment.content_type == "video/mp4"

    def test_create_with_valid_video_mov(self) -> None:
        post_id = EntityId.generate()
        attachment = MediaAttachment.create(
            post_id=post_id,
            url="https://cdn.example.com/video.mov",
            content_type="video/quicktime",
            file_size=15_000_000,
        )
        assert attachment.content_type == "video/quicktime"

    def test_create_with_valid_video_webm(self) -> None:
        post_id = EntityId.generate()
        attachment = MediaAttachment.create(
            post_id=post_id,
            url="https://cdn.example.com/video.webm",
            content_type="video/webm",
            file_size=8_000_000,
        )
        assert attachment.content_type == "video/webm"

    def test_attachment_is_frozen(self) -> None:
        post_id = EntityId.generate()
        attachment = MediaAttachment.create(
            post_id=post_id,
            url="https://cdn.example.com/image.jpg",
            content_type="image/jpeg",
            file_size=1024,
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            attachment.url = "https://cdn.example.com/other.jpg"  # type: ignore

    def test_invalid_content_type_raises_error(self) -> None:
        post_id = EntityId.generate()
        with pytest.raises(InvalidMediaTypeError, match="application/pdf"):
            MediaAttachment.create(
                post_id=post_id,
                url="https://cdn.example.com/file.pdf",
                content_type="application/pdf",
                file_size=1024,
            )

    def test_invalid_content_type_text_html(self) -> None:
        post_id = EntityId.generate()
        with pytest.raises(InvalidMediaTypeError):
            MediaAttachment.create(
                post_id=post_id,
                url="https://cdn.example.com/page.html",
                content_type="text/html",
                file_size=512,
            )

    def test_file_too_large_raises_error(self) -> None:
        post_id = EntityId.generate()
        max_size = 50 * 1024 * 1024  # 50MB
        with pytest.raises(MediaTooLargeError):
            MediaAttachment.create(
                post_id=post_id,
                url="https://cdn.example.com/huge.mp4",
                content_type="video/mp4",
                file_size=max_size + 1,
            )

    def test_file_at_exact_max_size_is_valid(self) -> None:
        post_id = EntityId.generate()
        max_size = 50 * 1024 * 1024  # 50MB
        attachment = MediaAttachment.create(
            post_id=post_id,
            url="https://cdn.example.com/big.mp4",
            content_type="video/mp4",
            file_size=max_size,
        )
        assert attachment.file_size == max_size

    def test_create_with_timestamps(self) -> None:
        post_id = EntityId.generate()
        created = datetime(2024, 1, 15, 12, 0, 0)
        attachment = MediaAttachment(
            id=EntityId.generate(),
            post_id=post_id,
            url="https://cdn.example.com/image.jpg",
            content_type="image/jpeg",
            file_size=1024,
            created_at=created,
        )
        assert attachment.created_at == created


class TestMediaExceptions:
    def test_media_error_is_base_exception(self) -> None:
        error = MediaError("Something went wrong")
        assert isinstance(error, Exception)
        assert error.message == "Something went wrong"
        assert str(error) == "Something went wrong"

    def test_media_error_default_message(self) -> None:
        error = MediaError()
        assert error.message == "Media error"

    def test_invalid_media_type_inherits_from_media_error(self) -> None:
        error = InvalidMediaTypeError("application/pdf")
        assert isinstance(error, MediaError)

    def test_media_too_large_inherits_from_media_error(self) -> None:
        error = MediaTooLargeError(100_000_000)
        assert isinstance(error, MediaError)

    def test_invalid_media_type_includes_type_in_message(self) -> None:
        error = InvalidMediaTypeError("application/pdf")
        assert "application/pdf" in str(error)

    def test_media_too_large_includes_size_in_message(self) -> None:
        error = MediaTooLargeError(100_000_000)
        assert "100000000" in str(error) or "100" in str(error)
