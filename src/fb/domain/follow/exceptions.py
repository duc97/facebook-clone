from __future__ import annotations


class FollowError(Exception):
    """Base exception for follow domain."""

    def __init__(self, message: str = "Follow error") -> None:
        self.message = message
        super().__init__(self.message)


class CannotFollowSelfError(FollowError):
    """Raised when a user tries to follow themselves."""

    def __init__(self) -> None:
        super().__init__("Cannot follow yourself")


class AlreadyFollowingError(FollowError):
    """Raised when user is already following the target."""

    def __init__(self) -> None:
        super().__init__("Already following this user")


class NotFollowingError(FollowError):
    """Raised when user is not following the target."""

    def __init__(self) -> None:
        super().__init__("Not following this user")
