from __future__ import annotations


class PostError(Exception):
    def __init__(self, message: str = "Post error") -> None:
        self.message = message
        super().__init__(self.message)


class PostNotFoundError(PostError):
    pass


class PostContentTooLongError(PostError):
    pass


class PostPermissionError(PostError):
    pass