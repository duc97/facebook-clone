from __future__ import annotations

import strawberry


@strawberry.type
class FriendRequestType:
    id: strawberry.ID
    sender_id: str
    receiver_id: str
    status: str


@strawberry.type
class FriendListType:
    friend_ids: list[str]
    total_count: int
