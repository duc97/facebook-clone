from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CreatePostInput:
    author_id: str
    content: str
    media_urls: list[str] | None = None


@dataclass(frozen=True, slots=True)
class UpdatePostInput:
    post_id: str
    user_id: str  # for authorization
    content: str | None = None


@dataclass(frozen=True, slots=True)
class DeletePostInput:
    post_id: str
    user_id: str


@dataclass(frozen=True, slots=True)
class GetPostInput:
    post_id: str


@dataclass(frozen=True, slots=True)
class GetPostsByAuthorInput:
    author_id: str
    limit: int = 20
    offset: int = 0


@dataclass(frozen=True, slots=True)
class PostOutput:
    id: str
    author_id: str
    content: str
    media_urls: list[str]
    like_count: int
    comment_count: int
    is_published: bool
    created_at: str | None = None