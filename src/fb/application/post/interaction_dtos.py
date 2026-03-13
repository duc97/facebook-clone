from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CreateCommentInput:
    post_id: str
    author_id: str
    content: str


@dataclass(frozen=True, slots=True)
class DeleteCommentInput:
    comment_id: str
    user_id: str  # for authorization


@dataclass(frozen=True, slots=True)
class LikePostInput:
    post_id: str
    user_id: str


@dataclass(frozen=True, slots=True)
class UnlikePostInput:
    post_id: str
    user_id: str


@dataclass(frozen=True, slots=True)
class CommentOutput:
    id: str
    post_id: str
    author_id: str
    content: str
    created_at: str | None = None


@dataclass(frozen=True, slots=True)
class LikeOutput:
    id: str
    post_id: str
    user_id: str


@dataclass(frozen=True, slots=True)
class CommentsListOutput:
    comments: list[CommentOutput]
    total_count: int
    has_next_page: bool


# ── Reaction DTOs ───────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ReactToPostInput:
    post_id: str
    user_id: str
    reaction_type: str


@dataclass(frozen=True, slots=True)
class RemoveReactionInput:
    post_id: str
    user_id: str


@dataclass(frozen=True, slots=True)
class ReactionOutput:
    id: str
    post_id: str
    user_id: str
    reaction_type: str
    created_at: str | None = None


# ── Share DTOs ──────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class SharePostInput:
    post_id: str
    user_id: str
    content: str = ""


@dataclass(frozen=True, slots=True)
class DeleteShareInput:
    share_id: str
    user_id: str


@dataclass(frozen=True, slots=True)
class ShareOutput:
    id: str
    post_id: str
    user_id: str
    content: str
    created_at: str | None = None