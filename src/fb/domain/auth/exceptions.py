from __future__ import annotations


class AuthError(Exception):
    """Base exception for auth domain."""

    def __init__(self, message: str = "Authentication error") -> None:
        self.message = message
        super().__init__(self.message)


class InvalidCredentialsError(AuthError):
    """Raised when login credentials are invalid."""

    def __init__(self) -> None:
        super().__init__("Invalid email or password")


class EmailAlreadyExistsError(AuthError):
    """Raised when email is already registered."""

    def __init__(self, email: str) -> None:
        super().__init__(f"Email already registered: {email}")
        self.email = email


class UserNameAlreadyExistsError(AuthError):
    """Raised when username is already registered."""

    def __init__(self, user_name: str) -> None:
        super().__init__(f"Username already taken: {user_name}")
        self.user_name = user_name


class UserNotFoundError(AuthError):
    """Raised when user is not found."""

    def __init__(self, identifier: str = "") -> None:
        msg = f"User not found: {identifier}" if identifier else "User not found"
        super().__init__(msg)


class UserInactiveError(AuthError):
    """Raised when user account is deactivated."""

    def __init__(self) -> None:
        super().__init__("User account is deactivated")


class InvalidTokenError(AuthError):
    """Raised when token is invalid or expired."""

    def __init__(self, reason: str = "Invalid or expired token") -> None:
        super().__init__(reason)


class TokenBlacklistedError(AuthError):
    """Raised when token has been blacklisted."""

    def __init__(self) -> None:
        super().__init__("Token has been revoked")
