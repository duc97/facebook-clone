from __future__ import annotations


class ProfileError(Exception):
    """Base exception for profile domain."""

    def __init__(self, message: str = "Profile error") -> None:
        self.message = message
        super().__init__(self.message)


class ProfileNotFoundError(ProfileError):
    """Raised when profile is not found."""

    def __init__(self, identifier: str = "") -> None:
        msg = f"Profile not found: {identifier}" if identifier else "Profile not found"
        super().__init__(msg)


class ProfileAlreadyExistsError(ProfileError):
    """Raised when profile already exists for a user."""

    def __init__(self, user_id: str) -> None:
        super().__init__(f"Profile already exists for user: {user_id}")
        self.user_id = user_id


class InvalidFileTypeError(ProfileError):
    """Raised when uploaded file type is not allowed."""

    def __init__(self, content_type: str) -> None:
        super().__init__(f"Invalid file type: {content_type}. Only image files are allowed.")
        self.content_type = content_type
