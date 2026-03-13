from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SendRequestInput:
    sender_id: str
    receiver_id: str


@dataclass(frozen=True, slots=True)
class AcceptRequestInput:
    request_id: str
    user_id: str  # user_id is the receiver


@dataclass(frozen=True, slots=True)
class RejectRequestInput:
    request_id: str
    user_id: str


@dataclass(frozen=True, slots=True)
class UnfriendInput:
    user_id: str
    friend_id: str


@dataclass(frozen=True, slots=True)
class BlockInput:
    user_id: str
    target_id: str


@dataclass(frozen=True, slots=True)
class MutualFriendsInput:
    user_id: str
    other_id: str


@dataclass(frozen=True, slots=True)
class FriendRequestOutput:
    id: str
    sender_id: str
    receiver_id: str
    status: str


@dataclass(frozen=True, slots=True)
class FriendListOutput:
    friend_ids: list[str]
    total_count: int
