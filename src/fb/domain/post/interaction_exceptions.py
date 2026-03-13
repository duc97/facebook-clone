from __future__ import annotations


class InteractionError(Exception):
    def __init__(self, message: str = "Interaction error") -> None:
        self.message = message
        super().__init__(self.message)


class CommentNotFoundError(InteractionError):
    pass


class AlreadyLikedError(InteractionError):
    pass


class NotLikedError(InteractionError):
    pass


class CommentPermissionError(InteractionError):
    pass


class AlreadyReactedError(InteractionError):
    pass


class ReactionNotFoundError(InteractionError):
    pass


class AlreadySharedError(InteractionError):
    pass


class ShareNotFoundError(InteractionError):
    pass


class CannotShareOwnPostError(InteractionError):
    pass


class SharePermissionError(InteractionError):
    pass