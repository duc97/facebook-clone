from __future__ import annotations

import strawberry


@strawberry.input
class UpdateProfileInput:
    bio: str | None = None
    location: str | None = None
    website: str | None = None
