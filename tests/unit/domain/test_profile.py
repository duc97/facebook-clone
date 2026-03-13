from __future__ import annotations

from datetime import date

import pytest

from fb.domain.profile.entities import Profile
from fb.domain.profile.exceptions import (
    InvalidFileTypeError,
    ProfileAlreadyExistsError,
    ProfileError,
    ProfileNotFoundError,
)
from fb.domain.shared.entity_id import EntityId


class TestProfileCreate:
    def test_create_profile(self) -> None:
        user_id = EntityId.generate()
        profile = Profile.create(user_id=user_id, bio="Hello world")
        assert profile.user_id == user_id
        assert profile.bio == "Hello world"
        assert isinstance(profile.id, EntityId)
        assert profile.avatar_url is None
        assert profile.cover_photo_url is None
        assert profile.location is None
        assert profile.website is None
        assert profile.date_of_birth is None

    def test_create_profile_defaults(self) -> None:
        user_id = EntityId.generate()
        profile = Profile.create(user_id=user_id)
        assert profile.bio == ""
        assert profile.avatar_url is None
        assert profile.cover_photo_url is None
        assert profile.location is None
        assert profile.website is None
        assert profile.date_of_birth is None

    def test_create_profile_with_all_fields(self) -> None:
        user_id = EntityId.generate()
        dob = date(1990, 5, 15)
        profile = Profile.create(
            user_id=user_id,
            bio="Full bio",
            avatar_url="https://example.com/avatar.jpg",
            cover_photo_url="https://example.com/cover.jpg",
            location="New York",
            website="https://example.com",
            date_of_birth=dob,
        )
        assert profile.bio == "Full bio"
        assert profile.avatar_url == "https://example.com/avatar.jpg"
        assert profile.cover_photo_url == "https://example.com/cover.jpg"
        assert profile.location == "New York"
        assert profile.website == "https://example.com"
        assert profile.date_of_birth == dob


class TestProfileUpdateBio:
    def test_update_bio_returns_new_instance(self) -> None:
        user_id = EntityId.generate()
        profile = Profile.create(user_id=user_id, bio="Old bio")
        updated = profile.update_bio("New bio")
        assert updated.bio == "New bio"
        assert profile.bio == "Old bio"  # original unchanged
        assert updated.id == profile.id
        assert updated.user_id == profile.user_id
        assert updated is not profile


class TestProfileUpdateAvatar:
    def test_update_avatar(self) -> None:
        profile = Profile.create(user_id=EntityId.generate())
        updated = profile.update_avatar("https://example.com/new-avatar.jpg")
        assert updated.avatar_url == "https://example.com/new-avatar.jpg"
        assert profile.avatar_url is None  # original unchanged
        assert updated.id == profile.id


class TestProfileUpdateCoverPhoto:
    def test_update_cover_photo(self) -> None:
        profile = Profile.create(user_id=EntityId.generate())
        updated = profile.update_cover_photo("https://example.com/cover.jpg")
        assert updated.cover_photo_url == "https://example.com/cover.jpg"
        assert profile.cover_photo_url is None  # original unchanged
        assert updated.id == profile.id


class TestProfileUpdateLocation:
    def test_update_location(self) -> None:
        profile = Profile.create(user_id=EntityId.generate())
        updated = profile.update_location("San Francisco")
        assert updated.location == "San Francisco"
        assert profile.location is None  # original unchanged
        assert updated.id == profile.id


class TestProfileUpdateWebsite:
    def test_update_website(self) -> None:
        profile = Profile.create(user_id=EntityId.generate())
        updated = profile.update_website("https://mysite.com")
        assert updated.website == "https://mysite.com"
        assert profile.website is None  # original unchanged
        assert updated.id == profile.id


class TestProfileFrozen:
    def test_frozen(self) -> None:
        profile = Profile.create(user_id=EntityId.generate(), bio="test")
        with pytest.raises(AttributeError):
            profile.bio = "changed"  # type: ignore[misc]


class TestProfileExceptions:
    def test_profile_error_base(self) -> None:
        err = ProfileError("custom message")
        assert str(err) == "custom message"
        assert err.message == "custom message"

    def test_profile_error_default_message(self) -> None:
        err = ProfileError()
        assert str(err) == "Profile error"

    def test_profile_not_found_error(self) -> None:
        err = ProfileNotFoundError("user-123")
        assert "user-123" in str(err)
        assert isinstance(err, ProfileError)

    def test_profile_not_found_error_no_identifier(self) -> None:
        err = ProfileNotFoundError()
        assert "Profile not found" in str(err)

    def test_profile_already_exists_error(self) -> None:
        err = ProfileAlreadyExistsError("user-456")
        assert "user-456" in str(err)
        assert isinstance(err, ProfileError)

    def test_invalid_file_type_error(self) -> None:
        err = InvalidFileTypeError("application/pdf")
        assert "application/pdf" in str(err)
        assert isinstance(err, ProfileError)
