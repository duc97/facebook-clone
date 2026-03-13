from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from fb.application.friend.dtos import (
    AcceptRequestInput,
    FriendListOutput,
    FriendRequestOutput,
    MutualFriendsInput,
    RejectRequestInput,
    SendRequestInput,
    UnfriendInput,
)
from fb.application.friend.send_request import SendRequestUseCase
from fb.application.friend.accept_request import AcceptRequestUseCase
from fb.application.friend.reject_request import RejectRequestUseCase
from fb.application.friend.unfriend import UnfriendUseCase
from fb.application.friend.mutual_friends import MutualFriendsUseCase
from fb.domain.friend.entities import FriendRequest, Friendship
from fb.domain.friend.exceptions import (
    AlreadyFriendsError,
    CannotFriendSelfError,
    FriendRequestAlreadyExistsError,
    FriendRequestNotFoundError,
    NotFriendsError,
    UserBlockedError,
)
from fb.domain.friend.value_objects import FriendRequestStatus
from fb.domain.shared.entity_id import EntityId


# ─── Fakes ──────────────────────────────────────────────


class FakeFriendRepo:
    def __init__(self) -> None:
        self._requests: dict[str, FriendRequest] = {}
        self._friendships: dict[str, Friendship] = {}

    async def find_request(
        self, sender_id: EntityId, receiver_id: EntityId
    ) -> FriendRequest | None:
        for req in self._requests.values():
            if req.sender_id == sender_id and req.receiver_id == receiver_id:
                return req
        return None

    async def find_request_by_id(self, request_id: EntityId) -> FriendRequest | None:
        return self._requests.get(str(request_id))

    async def save_request(self, request: FriendRequest) -> FriendRequest:
        self._requests[str(request.id)] = request
        return request

    async def update_request(self, request: FriendRequest) -> FriendRequest:
        self._requests[str(request.id)] = request
        return request

    async def save_friendship(self, friendship: Friendship) -> Friendship:
        self._friendships[str(friendship.id)] = friendship
        return friendship

    async def delete_friendship(
        self, user_id: EntityId, friend_id: EntityId
    ) -> None:
        to_delete = [
            fid
            for fid, f in self._friendships.items()
            if (f.user_id == user_id and f.friend_id == friend_id)
            or (f.user_id == friend_id and f.friend_id == user_id)
        ]
        for fid in to_delete:
            del self._friendships[fid]

    async def are_friends(self, user_id: EntityId, friend_id: EntityId) -> bool:
        return any(
            f.user_id == user_id and f.friend_id == friend_id
            for f in self._friendships.values()
        )

    async def get_friends(
        self, user_id: EntityId, limit: int = 20, offset: int = 0
    ) -> list[EntityId]:
        friends = [
            f.friend_id
            for f in self._friendships.values()
            if f.user_id == user_id
        ]
        return friends[offset : offset + limit]

    async def get_pending_requests(
        self, user_id: EntityId
    ) -> list[FriendRequest]:
        return [
            req
            for req in self._requests.values()
            if req.receiver_id == user_id
            and req.status == FriendRequestStatus.PENDING
        ]

    async def get_mutual_friends(
        self, user_id: EntityId, other_id: EntityId
    ) -> list[EntityId]:
        user_friends = {
            f.friend_id
            for f in self._friendships.values()
            if f.user_id == user_id
        }
        other_friends = {
            f.friend_id
            for f in self._friendships.values()
            if f.user_id == other_id
        }
        return list(user_friends & other_friends)

    async def get_friend_count(self, user_id: EntityId) -> int:
        return sum(
            1
            for f in self._friendships.values()
            if f.user_id == user_id
        )


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> FakeUnitOfWork:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        if exc_type is not None:
            self.rolled_back = True

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


# ─── Fixtures ──────────────────────────────────────────────


@pytest.fixture
def friend_repo() -> FakeFriendRepo:
    return FakeFriendRepo()


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


# ─── Helper ──────────────────────────────────────────────


def _add_friendship_pair(
    repo: FakeFriendRepo,
    user_id: EntityId,
    friend_id: EntityId,
) -> None:
    """Add bi-directional friendship entries to the fake repo."""
    f1, f2 = Friendship.create_pair(user_id=user_id, friend_id=friend_id)
    repo._friendships[str(f1.id)] = f1
    repo._friendships[str(f2.id)] = f2


def _add_pending_request(
    repo: FakeFriendRepo,
    sender_id: EntityId,
    receiver_id: EntityId,
) -> FriendRequest:
    """Add a pending friend request to the fake repo."""
    req = FriendRequest.create(sender_id=sender_id, receiver_id=receiver_id)
    repo._requests[str(req.id)] = req
    return req


def _add_blocked_request(
    repo: FakeFriendRepo,
    sender_id: EntityId,
    receiver_id: EntityId,
) -> FriendRequest:
    """Add a blocked friend request to the fake repo."""
    req = FriendRequest.create(sender_id=sender_id, receiver_id=receiver_id).block()
    repo._requests[str(req.id)] = req
    return req


# ─── SendRequest Tests ──────────────────────────────────


class TestSendRequest:
    async def test_success(
        self, friend_repo: FakeFriendRepo, uow: FakeUnitOfWork
    ) -> None:
        sender = EntityId.generate()
        receiver = EntityId.generate()

        use_case = SendRequestUseCase(friend_repo, uow)
        result = await use_case.execute(
            SendRequestInput(sender_id=str(sender), receiver_id=str(receiver))
        )

        assert isinstance(result, FriendRequestOutput)
        assert result.sender_id == str(sender)
        assert result.receiver_id == str(receiver)
        assert result.status == "pending"
        assert uow.committed is True

    async def test_cannot_self(
        self, friend_repo: FakeFriendRepo, uow: FakeUnitOfWork
    ) -> None:
        user = EntityId.generate()
        use_case = SendRequestUseCase(friend_repo, uow)

        with pytest.raises(CannotFriendSelfError):
            await use_case.execute(
                SendRequestInput(sender_id=str(user), receiver_id=str(user))
            )

    async def test_already_friends(
        self, friend_repo: FakeFriendRepo, uow: FakeUnitOfWork
    ) -> None:
        sender = EntityId.generate()
        receiver = EntityId.generate()
        _add_friendship_pair(friend_repo, sender, receiver)

        use_case = SendRequestUseCase(friend_repo, uow)

        with pytest.raises(AlreadyFriendsError):
            await use_case.execute(
                SendRequestInput(sender_id=str(sender), receiver_id=str(receiver))
            )

    async def test_already_pending(
        self, friend_repo: FakeFriendRepo, uow: FakeUnitOfWork
    ) -> None:
        sender = EntityId.generate()
        receiver = EntityId.generate()
        _add_pending_request(friend_repo, sender, receiver)

        use_case = SendRequestUseCase(friend_repo, uow)

        with pytest.raises(FriendRequestAlreadyExistsError):
            await use_case.execute(
                SendRequestInput(sender_id=str(sender), receiver_id=str(receiver))
            )

    async def test_user_blocked(
        self, friend_repo: FakeFriendRepo, uow: FakeUnitOfWork
    ) -> None:
        sender = EntityId.generate()
        receiver = EntityId.generate()
        _add_blocked_request(friend_repo, sender, receiver)

        use_case = SendRequestUseCase(friend_repo, uow)

        with pytest.raises(UserBlockedError):
            await use_case.execute(
                SendRequestInput(sender_id=str(sender), receiver_id=str(receiver))
            )


# ─── AcceptRequest Tests ──────────────────────────────────


class TestAcceptRequest:
    async def test_success(
        self, friend_repo: FakeFriendRepo, uow: FakeUnitOfWork
    ) -> None:
        sender = EntityId.generate()
        receiver = EntityId.generate()
        req = _add_pending_request(friend_repo, sender, receiver)

        use_case = AcceptRequestUseCase(friend_repo, uow)
        result = await use_case.execute(
            AcceptRequestInput(request_id=str(req.id), user_id=str(receiver))
        )

        assert isinstance(result, FriendRequestOutput)
        assert result.status == "accepted"
        # Should create bi-directional friendships
        assert await friend_repo.are_friends(sender, receiver)
        assert await friend_repo.are_friends(receiver, sender)
        assert uow.committed is True

    async def test_not_found(
        self, friend_repo: FakeFriendRepo, uow: FakeUnitOfWork
    ) -> None:
        fake_id = EntityId.generate()
        user = EntityId.generate()

        use_case = AcceptRequestUseCase(friend_repo, uow)

        with pytest.raises(FriendRequestNotFoundError):
            await use_case.execute(
                AcceptRequestInput(request_id=str(fake_id), user_id=str(user))
            )

    async def test_not_pending(
        self, friend_repo: FakeFriendRepo, uow: FakeUnitOfWork
    ) -> None:
        sender = EntityId.generate()
        receiver = EntityId.generate()
        req = _add_pending_request(friend_repo, sender, receiver)
        # Reject it first so it's no longer PENDING
        rejected = req.reject()
        friend_repo._requests[str(rejected.id)] = rejected

        use_case = AcceptRequestUseCase(friend_repo, uow)

        with pytest.raises(FriendRequestNotFoundError):
            await use_case.execute(
                AcceptRequestInput(
                    request_id=str(rejected.id), user_id=str(receiver)
                )
            )

    async def test_wrong_receiver(
        self, friend_repo: FakeFriendRepo, uow: FakeUnitOfWork
    ) -> None:
        sender = EntityId.generate()
        receiver = EntityId.generate()
        wrong_user = EntityId.generate()
        req = _add_pending_request(friend_repo, sender, receiver)

        use_case = AcceptRequestUseCase(friend_repo, uow)

        with pytest.raises(FriendRequestNotFoundError):
            await use_case.execute(
                AcceptRequestInput(
                    request_id=str(req.id), user_id=str(wrong_user)
                )
            )


# ─── RejectRequest Tests ──────────────────────────────────


class TestRejectRequest:
    async def test_success(
        self, friend_repo: FakeFriendRepo, uow: FakeUnitOfWork
    ) -> None:
        sender = EntityId.generate()
        receiver = EntityId.generate()
        req = _add_pending_request(friend_repo, sender, receiver)

        use_case = RejectRequestUseCase(friend_repo, uow)
        result = await use_case.execute(
            RejectRequestInput(request_id=str(req.id), user_id=str(receiver))
        )

        assert isinstance(result, FriendRequestOutput)
        assert result.status == "rejected"
        assert uow.committed is True

    async def test_not_found(
        self, friend_repo: FakeFriendRepo, uow: FakeUnitOfWork
    ) -> None:
        fake_id = EntityId.generate()
        user = EntityId.generate()

        use_case = RejectRequestUseCase(friend_repo, uow)

        with pytest.raises(FriendRequestNotFoundError):
            await use_case.execute(
                RejectRequestInput(request_id=str(fake_id), user_id=str(user))
            )

    async def test_wrong_receiver(
        self, friend_repo: FakeFriendRepo, uow: FakeUnitOfWork
    ) -> None:
        sender = EntityId.generate()
        receiver = EntityId.generate()
        wrong_user = EntityId.generate()
        req = _add_pending_request(friend_repo, sender, receiver)

        use_case = RejectRequestUseCase(friend_repo, uow)

        with pytest.raises(FriendRequestNotFoundError):
            await use_case.execute(
                RejectRequestInput(
                    request_id=str(req.id), user_id=str(wrong_user)
                )
            )


# ─── Unfriend Tests ──────────────────────────────────


class TestUnfriend:
    async def test_success(
        self, friend_repo: FakeFriendRepo, uow: FakeUnitOfWork
    ) -> None:
        user = EntityId.generate()
        friend = EntityId.generate()
        _add_friendship_pair(friend_repo, user, friend)

        use_case = UnfriendUseCase(friend_repo, uow)
        await use_case.execute(
            UnfriendInput(user_id=str(user), friend_id=str(friend))
        )

        assert not await friend_repo.are_friends(user, friend)
        assert not await friend_repo.are_friends(friend, user)
        assert uow.committed is True

    async def test_not_friends(
        self, friend_repo: FakeFriendRepo, uow: FakeUnitOfWork
    ) -> None:
        user = EntityId.generate()
        other = EntityId.generate()

        use_case = UnfriendUseCase(friend_repo, uow)

        with pytest.raises(NotFriendsError):
            await use_case.execute(
                UnfriendInput(user_id=str(user), friend_id=str(other))
            )


# ─── MutualFriends Tests ──────────────────────────────────


class TestMutualFriends:
    async def test_success(
        self, friend_repo: FakeFriendRepo, uow: FakeUnitOfWork
    ) -> None:
        user_a = EntityId.generate()
        user_b = EntityId.generate()
        mutual_1 = EntityId.generate()
        mutual_2 = EntityId.generate()

        # Both are friends with mutual_1 and mutual_2
        _add_friendship_pair(friend_repo, user_a, mutual_1)
        _add_friendship_pair(friend_repo, user_a, mutual_2)
        _add_friendship_pair(friend_repo, user_b, mutual_1)
        _add_friendship_pair(friend_repo, user_b, mutual_2)

        use_case = MutualFriendsUseCase(friend_repo)
        result = await use_case.execute(
            MutualFriendsInput(user_id=str(user_a), other_id=str(user_b))
        )

        assert isinstance(result, FriendListOutput)
        result_ids = set(result.friend_ids)
        assert str(mutual_1) in result_ids
        assert str(mutual_2) in result_ids
        assert result.total_count == 2

    async def test_no_mutual(
        self, friend_repo: FakeFriendRepo, uow: FakeUnitOfWork
    ) -> None:
        user_a = EntityId.generate()
        user_b = EntityId.generate()
        friend_a = EntityId.generate()
        friend_b = EntityId.generate()

        _add_friendship_pair(friend_repo, user_a, friend_a)
        _add_friendship_pair(friend_repo, user_b, friend_b)

        use_case = MutualFriendsUseCase(friend_repo)
        result = await use_case.execute(
            MutualFriendsInput(user_id=str(user_a), other_id=str(user_b))
        )

        assert isinstance(result, FriendListOutput)
        assert result.friend_ids == []
        assert result.total_count == 0
