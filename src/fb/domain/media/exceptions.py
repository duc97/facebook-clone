from __future__ import annotations


class MediaError(Exception):
    def __init__(self, message: str = "Media error") -> None:
        self.message = message
        super().__init__(self.message)


class InvalidMediaTypeError(MediaError):
    def __init__(self, content_type: str) -> None:
        super().__init__(f"Unsupported media type: {content_type}")


class MediaTooLargeError(MediaError):
    def __init__(self, size: int, max_size: int) -> None:
        super().__init__(f"File {size} bytes exceeds limit of {max_size} bytes")


class MediaNotFoundError(MediaError):
    def __init__(self) -> None:
        super().__init__("Media not found")


class MediaOwnershipError(MediaError):
    def __init__(self) -> None:
        super().__init__("You do not own this media")
