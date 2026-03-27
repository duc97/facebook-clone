from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator


# ── Auth ─────────────────────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    user_name: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.]+$")
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    birthday: str | None = Field(default=None, description="YYYY-MM-DD format")


class LoginRequest(BaseModel):
    user_name: str
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str = ""


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    user_name: str
    email: str
    first_name: str
    last_name: str
    display_name: str
    is_active: bool


class EditUserRequest(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=50)
    last_name: str | None = Field(default=None, min_length=1, max_length=50)
    birthday: str | None = Field(default=None, description="YYYY-MM-DD format")
    password: str | None = Field(default=None, min_length=6, max_length=128)


# ── Profile ──────────────────────────────────────────────────────────────────


class ProfileUpdateRequest(BaseModel):
    bio: str | None = None
    location: str | None = None
    website: str | None = None


class ProfileResponse(BaseModel):
    id: str
    user_id: str
    bio: str
    avatar_url: str | None
    cover_photo_url: str | None
    location: str | None
    website: str | None
    display_name: str


# ── Friend / Follow ─────────────────────────────────────────────────────────


class SendFriendRequestBody(BaseModel):
    receiver_id: str


class FriendRequestResponse(BaseModel):
    id: str
    sender_id: str
    receiver_id: str
    status: str


class FriendListResponse(BaseModel):
    friend_ids: list[str]
    total_count: int


class FollowListResponse(BaseModel):
    users: list[str]
    total_count: int


class MessageResponse(BaseModel):
    message: str


# ── Post ─────────────────────────────────────────────────────────────────────


class PostCreateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    image: str | None = None


class PostUpdateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    image: str | None = None


class PostResponse(BaseModel):
    id: str
    author_id: str
    text: str
    image: str | None
    like_count: int
    comment_count: int
    is_published: bool
    created_at: str | None = None


class CommentCreateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)


class CommentResponse(BaseModel):
    id: str
    post_id: str
    author_id: str
    text: str
    created_at: str | None = None


class LikeResponse(BaseModel):
    id: str
    post_id: str
    user_id: str


# ── Media ──────────────────────────────────────────────────────────────


class MediaUploadResponse(BaseModel):
    url: str
    content_type: str
    file_size: int


# ── Reaction ────────────────────────────────────────────────────────────


_VALID_REACTION_TYPES = {"LIKE", "LOVE", "HAHA", "WOW", "SAD", "ANGRY"}


class ReactionRequest(BaseModel):
    reaction_type: str

    @field_validator("reaction_type")
    @classmethod
    def _validate_reaction_type(cls, v: str) -> str:
        upper = v.upper()
        if upper not in _VALID_REACTION_TYPES:
            raise ValueError(
                f"Invalid reaction type '{v}'. Must be one of: {', '.join(sorted(_VALID_REACTION_TYPES))}"
            )
        return upper


class ReactionResponse(BaseModel):
    id: str
    post_id: str
    user_id: str
    reaction_type: str
    created_at: str | None = None


class ReactionCountResponse(BaseModel):
    reaction_type: str
    count: int


class ReactionsListResponse(BaseModel):
    reactions: list[ReactionResponse]
    counts: dict[str, int]
    total_count: int


# ── Share ───────────────────────────────────────────────────────────────


class ShareRequest(BaseModel):
    content: str = ""


class ShareResponse(BaseModel):
    id: str
    post_id: str
    user_id: str
    content: str
    created_at: str | None = None


# ── Feed ────────────────────────────────────────────────────────────────


class FeedPostResponse(BaseModel):
    """Feed post response with created_at always present and optional score."""

    id: str
    author_id: str
    text: str
    image: str | None = None
    like_count: int
    comment_count: int
    created_at: str | None = None
    score: float | None = None


class FeedResponse(BaseModel):
    """Paginated feed response."""

    posts: list[FeedPostResponse]
    total_count: int
    has_next_page: bool


# ── Notification ──────────────────────────────────────────────────────


class NotificationResponse(BaseModel):
    id: str
    user_id: str
    actor_id: str
    notification_type: str
    entity_id: str
    entity_type: str
    message: str
    is_read: bool
    created_at: str | None = None


class NotificationsListResponse(BaseModel):
    notifications: list[NotificationResponse]
    unread_count: int
    total_count: int


class UnreadCountResponse(BaseModel):
    unread_count: int


# ── Chat / Messages ──────────────────────────────────────────────────


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


class ChatMessageResponse(BaseModel):
    id: str
    sender_id: str
    receiver_id: str
    content: str
    is_seen: bool
    created_at: str | None = None


class ChatConversationResponse(BaseModel):
    other_user_id: str
    last_message: ChatMessageResponse | None = None
    unread_count: int


class UnreadMessagesResponse(BaseModel):
    unread_count: int


# ── Media Upload ──────────────────────────────────────────────────────

class MediaUploadRequest(BaseModel):
    entity_type: str = Field(..., description="post|avatar|cover|chat")
    entity_id: str = Field(default="")


class MediaInfoResponse(BaseModel):
    id: str
    owner_id: str
    entity_id: str
    entity_type: str
    original_url: str
    thumbnail_url: str | None = None
    processed_url: str | None = None
    media_type: str
    content_type: str
    file_size: int
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    status: str
    created_at: str | None = None
