from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProfileOutput:
    id: str
    user_id: str
    bio: str
    avatar_url: str | None
    cover_photo_url: str | None
    location: str | None
    website: str | None
    display_name: str


@dataclass(frozen=True, slots=True)
class UpdateProfileInput:
    user_id: str
    bio: str | None = None
    location: str | None = None
    website: str | None = None


@dataclass(frozen=True, slots=True)
class UploadAvatarInput:
    user_id: str
    file_data: bytes
    filename: str
    content_type: str
