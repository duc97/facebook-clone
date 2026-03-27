from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FollowInput:
    follower_id: str
    following_id: str


@dataclass(frozen=True, slots=True)
class UnfollowInput:
    follower_id: str
    following_id: str


@dataclass(frozen=True, slots=True)
class FollowListOutput:
    user_ids: list[str]
    total_count: int
