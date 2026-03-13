from __future__ import annotations

import pytest

from fb.domain.auth.entities import User
from fb.domain.auth.value_objects import Email, HashedPassword, TokenPair
from fb.domain.auth.exceptions import (
    AuthError,
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenBlacklistedError,
    UserInactiveError,
    UserNotFoundError,
)
from fb.domain.shared.entity_id import EntityId


class TestEmail:
    def test_valid_email(self) -> None:
        email = Email("user@example.com")
        assert email.value == "user@example.com"
        assert str(email) == "user@example.com"

    def test_valid_email_with_dots(self) -> None:
        email = Email("first.last@example.co.uk")
        assert email.value == "first.last@example.co.uk"

    def test_valid_email_with_plus(self) -> None:
        email = Email("user+tag@example.com")
        assert email.value == "user+tag@example.com"

    def test_invalid_email_no_at(self) -> None:
        with pytest.raises(ValueError, match="Invalid email"):
            Email("invalid-email")

    def test_invalid_email_no_domain(self) -> None:
        with pytest.raises(ValueError, match="Invalid email"):
            Email("user@")

    def test_invalid_email_empty(self) -> None:
        with pytest.raises(ValueError, match="Invalid email"):
            Email("")

    def test_email_is_frozen(self) -> None:
        email = Email("user@example.com")
        with pytest.raises(AttributeError):
            email.value = "other@example.com"  # type: ignore[misc]

    def test_email_equality(self) -> None:
        e1 = Email("user@example.com")
        e2 = Email("user@example.com")
        assert e1 == e2

    def test_email_inequality(self) -> None:
        e1 = Email("user1@example.com")
        e2 = Email("user2@example.com")
        assert e1 != e2


class TestHashedPassword:
    def test_valid_hashed_password(self) -> None:
        hp = HashedPassword("$2b$12$somehash")
        assert hp.value == "$2b$12$somehash"

    def test_empty_hashed_password_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            HashedPassword("")

    def test_str_hides_value(self) -> None:
        hp = HashedPassword("$2b$12$somehash")
        assert str(hp) == "***"

    def test_repr_hides_value(self) -> None:
        hp = HashedPassword("$2b$12$somehash")
        assert repr(hp) == "HashedPassword(***)"

    def test_frozen(self) -> None:
        hp = HashedPassword("$2b$12$somehash")
        with pytest.raises(AttributeError):
            hp.value = "new"  # type: ignore[misc]


class TestTokenPair:
    def test_create_token_pair(self) -> None:
        tp = TokenPair(access_token="acc", refresh_token="ref")
        assert tp.access_token == "acc"
        assert tp.refresh_token == "ref"
        assert tp.token_type == "bearer"

    def test_custom_token_type(self) -> None:
        tp = TokenPair(access_token="a", refresh_token="r", token_type="custom")
        assert tp.token_type == "custom"

    def test_frozen(self) -> None:
        tp = TokenPair(access_token="a", refresh_token="r")
        with pytest.raises(AttributeError):
            tp.access_token = "new"  # type: ignore[misc]


class TestUser:
    def test_create_user(self) -> None:
        user = User.create(
            email="test@example.com",
            hashed_password="$2b$12$hash",
            display_name="Test User",
        )
        assert str(user.email) == "test@example.com"
        assert user.display_name == "Test User"
        assert user.is_active is True
        assert isinstance(user.id, EntityId)

    def test_create_user_invalid_email(self) -> None:
        with pytest.raises(ValueError, match="Invalid email"):
            User.create(
                email="not-an-email",
                hashed_password="$2b$12$hash",
                display_name="Test",
            )

    def test_user_is_frozen(self) -> None:
        user = User.create(
            email="test@example.com",
            hashed_password="$2b$12$hash",
            display_name="Test",
        )
        with pytest.raises(AttributeError):
            user.display_name = "Changed"  # type: ignore[misc]

    def test_deactivate_returns_new_user(self) -> None:
        user = User.create(
            email="test@example.com",
            hashed_password="$2b$12$hash",
            display_name="Test",
        )
        deactivated = user.deactivate()
        assert deactivated.is_active is False
        assert user.is_active is True  # original unchanged
        assert deactivated.id == user.id
        assert deactivated.email == user.email

    def test_change_password_returns_new_user(self) -> None:
        user = User.create(
            email="test@example.com",
            hashed_password="$2b$12$oldhash",
            display_name="Test",
        )
        updated = user.change_password("$2b$12$newhash")
        assert updated.hashed_password.value == "$2b$12$newhash"
        assert user.hashed_password.value == "$2b$12$oldhash"  # original unchanged
        assert updated.id == user.id

    def test_update_display_name_returns_new_user(self) -> None:
        user = User.create(
            email="test@example.com",
            hashed_password="$2b$12$hash",
            display_name="Old Name",
        )
        updated = user.update_display_name("New Name")
        assert updated.display_name == "New Name"
        assert user.display_name == "Old Name"  # original unchanged
        assert updated.id == user.id

    def test_user_equality_by_id(self) -> None:
        eid = EntityId.generate()
        u1 = User(
            id=eid,
            email=Email("a@b.com"),
            hashed_password=HashedPassword("hash1"),
            display_name="User1",
        )
        u2 = User(
            id=eid,
            email=Email("a@b.com"),
            hashed_password=HashedPassword("hash2"),
            display_name="User2",
        )
        # frozen dataclasses compare all fields by default
        assert u1.id == u2.id


class TestAuthExceptions:
    def test_auth_error(self) -> None:
        err = AuthError("custom message")
        assert str(err) == "custom message"
        assert err.message == "custom message"

    def test_auth_error_default_message(self) -> None:
        err = AuthError()
        assert str(err) == "Authentication error"

    def test_invalid_credentials(self) -> None:
        err = InvalidCredentialsError()
        assert "Invalid email or password" in str(err)
        assert isinstance(err, AuthError)

    def test_email_already_exists(self) -> None:
        err = EmailAlreadyExistsError("test@example.com")
        assert "test@example.com" in str(err)
        assert err.email == "test@example.com"
        assert isinstance(err, AuthError)

    def test_user_not_found(self) -> None:
        err = UserNotFoundError("user-123")
        assert "user-123" in str(err)
        assert isinstance(err, AuthError)

    def test_user_not_found_no_identifier(self) -> None:
        err = UserNotFoundError()
        assert "User not found" in str(err)

    def test_user_inactive(self) -> None:
        err = UserInactiveError()
        assert "deactivated" in str(err)
        assert isinstance(err, AuthError)

    def test_invalid_token(self) -> None:
        err = InvalidTokenError()
        assert "Invalid or expired" in str(err)
        assert isinstance(err, AuthError)

    def test_invalid_token_custom_reason(self) -> None:
        err = InvalidTokenError("Token expired")
        assert str(err) == "Token expired"

    def test_token_blacklisted(self) -> None:
        err = TokenBlacklistedError()
        assert "revoked" in str(err)
        assert isinstance(err, AuthError)
