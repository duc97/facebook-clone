from __future__ import annotations

import strawberry


@strawberry.type
class ProfileType:
    id: strawberry.ID
    user_id: strawberry.ID
    bio: str
    avatar_url: str | None
    cover_photo_url: str | None
    location: str | None
    website: str | None
    display_name: str
