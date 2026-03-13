from __future__ import annotations


class FriendError(Exception):
    """Base exception for friend domain."""

    def __init__(self, message: str = "Friend error") -> None:
        self.message = message
        super().__init__(self.message)


class FriendRequestAlreadyExistsError(FriendError):
    """Raised when a friend request already exists between two users."""

    def __init__(self) -> None:
        super().__init__("Friend request already exists")


class FriendRequestNotFoundError(FriendError):
    """Raised when a friend request is not found."""

    def __init__(self) -> None:
        super().__init__("Friend request not found")


class CannotFriendSelfError(FriendError):
    """Raised when a user tries to send a friend request to themselves."""

    def __init__(self) -> None:
        super().__init__("Cannot send friend request to yourself")


class AlreadyFriendsError(FriendError):
    """Raised when users are already friends."""

    def __init__(self) -> None:
        super().__init__("Already friends with this user")


class NotFriendsError(FriendError):
    """Raised when users are not friends."""

    def __init__(self) -> None:
        super().__init__("Not friends with this user")


class UserBlockedError(FriendError):
    """Raised when a user is blocked."""

    def __init__(self) -> None:
        super().__init__("User is blocked")
