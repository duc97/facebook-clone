from __future__ import annotations

import strawberry


@strawberry.input
class CreatePostInput:
    content: str
    media_urls: list[str] | None = None


@strawberry.input
class UpdatePostInput:
    post_id: strawberry.ID
    content: str | None = None


@strawberry.input
class DeletePostInput:
    post_id: strawberry.ID