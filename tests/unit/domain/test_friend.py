from __future__ import annotations

import pytest

from fb.domain.friend.value_objects import FriendRequestStatus
from fb.domain.friend.entities import FriendRequest, Friendship
from fb.domain.friend.exceptions import (
    AlreadyFriendsError,
    CannotFriendSelfError,
    FriendError,
    FriendRequestAlreadyExistsError,
    FriendRequestNotFoundError,
    NotFriendsError,
    UserBlockedError,
)
from fb.domain.shared.entity_id import EntityId


# ─── FriendRequestStatus ──────────────────────────────────────


class TestFriendRequestStatus:
    def test_pending_value(self) -> None:
        assert FriendRequestStatus.PENDING.value == "pending"

    def test_accepted_value(self) -> None:
        assert FriendRequestStatus.ACCEPTED.value == "accepted"

    def test_rejected_value(self) -> None:
        assert FriendRequestStatus.REJECTED.value == "rejected"

    def test_blocked_value(self) -> None:
        assert FriendRequestStatus.BLOCKED.value == "blocked"

    def test_all_values(self) -> None:
        values = {s.value for s in FriendRequestStatus}
        assert values == {"pending", "accepted", "rejected", "blocked"}


# ─── FriendRequest ──────────────────────────────────────


class TestFriendRequest:
    def test_create(self) -> None:
        sender = EntityId.generate()
        receiver = EntityId.generate()
        request = FriendRequest.create(sender_id=sender, receiver_id=receiver)

        assert isinstance(request.id, EntityId)
        assert request.sender_id == sender
        assert request.receiver_id == receiver
        assert request.status == FriendRequestStatus.PENDING
        assert request.created_at is None
        assert request.updated_at is None

    def test_accept_returns_new(self) -> None:
        sender = EntityId.generate()
        receiver = EntityId.generate()
        original = FriendRequest.create(sender_id=sender, receiver_id=receiver)
        accepted = original.accept()

        assert accepted.status == FriendRequestStatus.ACCEPTED
        assert original.status == FriendRequestStatus.PENDING  # original unchanged
        assert accepted.id == original.id
        assert accepted.sender_id == original.sender_id
        assert accepted.receiver_id == original.receiver_id

    def test_reject_returns_new(self) -> None:
        sender = EntityId.generate()
        receiver = EntityId.generate()
        original = FriendRequest.create(sender_id=sender, receiver_id=receiver)
        rejected = original.reject()

        assert rejected.status == FriendRequestStatus.REJECTED
        assert original.status == FriendRequestStatus.PENDING  # original unchanged
        assert rejected.id == original.id
        assert rejected.sender_id == original.sender_id
        assert rejected.receiver_id == original.receiver_id

    def test_block_returns_new(self) -> None:
        sender = EntityId.generate()
        receiver = EntityId.generate()
        original = FriendRequest.create(sender_id=sender, receiver_id=receiver)
        blocked = original.block()

        assert blocked.status == FriendRequestStatus.BLOCKED
        assert original.status == FriendRequestStatus.PENDING  # original unchanged
        assert blocked.id == original.id
        assert blocked.sender_id == original.sender_id
        assert blocked.receiver_id == original.receiver_id

    def test_frozen(self) -> None:
        request = FriendRequest.create(
            sender_id=EntityId.generate(),
            receiver_id=EntityId.generate(),
        )
        with pytest.raises(AttributeError):
            request.status = FriendRequestStatus.ACCEPTED  # type: ignore[misc]


# ─── Friendship ──────────────────────────────────────


class TestFriendship:
    def test_create_pair_returns_two(self) -> None:
        user = EntityId.generate()
        friend = EntityId.generate()
        pair = Friendship.create_pair(user_id=user, friend_id=friend)

        assert len(pair) == 2
        assert isinstance(pair[0], Friendship)
        assert isinstance(pair[1], Friendship)

    def test_create_pair_bidirectional(self) -> None:
        user = EntityId.generate()
        friend = EntityId.generate()
        f1, f2 = Friendship.create_pair(user_id=user, friend_id=friend)

        assert f1.user_id == user
        assert f1.friend_id == friend
        assert f2.user_id == friend
        assert f2.friend_id == user

    def test_create_pair_distinct_ids(self) -> None:
        user = EntityId.generate()
        friend = EntityId.generate()
        f1, f2 = Friendship.create_pair(user_id=user, friend_id=friend)

        assert f1.id != f2.id

    def test_frozen(self) -> None:
        user = EntityId.generate()
        friend = EntityId.generate()
        f1, _ = Friendship.create_pair(user_id=user, friend_id=friend)

        with pytest.raises(AttributeError):
            f1.user_id = EntityId.generate()  # type: ignore[misc]


# ─── Exceptions ──────────────────────────────────────


class TestFriendExceptions:
    def test_friend_error_base(self) -> None:
        err = FriendError("something went wrong")
        assert str(err) == "something went wrong"
        assert err.message == "something went wrong"
        assert isinstance(err, Exception)

    def test_friend_error_default_message(self) -> None:
        err = FriendError()
        assert str(err) == "Friend error"

    def test_friend_request_already_exists(self) -> None:
        err = FriendRequestAlreadyExistsError()
        assert isinstance(err, FriendError)
        assert "already" in str(err).lower()

    def test_friend_request_not_found(self) -> None:
        err = FriendRequestNotFoundError()
        assert isinstance(err, FriendError)
        assert "not found" in str(err).lower()

    def test_cannot_friend_self(self) -> None:
        err = CannotFriendSelfError()
        assert isinstance(err, FriendError)
        assert "yourself" in str(err).lower() or "self" in str(err).lower()

    def test_already_friends(self) -> None:
        err = AlreadyFriendsError()
        assert isinstance(err, FriendError)
        assert "already" in str(err).lower()

    def test_not_friends(self) -> None:
        err = NotFriendsError()
        assert isinstance(err, FriendError)
        assert "not friends" in str(err).lower()

    def test_user_blocked(self) -> None:
        err = UserBlockedError()
        assert isinstance(err, FriendError)
        assert "blocked" in str(err).lower()

    def test_all_inherit_from_friend_error(self) -> None:
        exceptions = [
            FriendRequestAlreadyExistsError(),
            FriendRequestNotFoundError(),
            CannotFriendSelfError(),
            AlreadyFriendsError(),
            NotFriendsError(),
            UserBlockedError(),
        ]
        for exc in exceptions:
            assert isinstance(exc, FriendError)
            assert isinstance(exc, Exception)
