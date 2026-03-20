from __future__ import annotations

from sqlalchemy import and_, delete, func, over, select
from sqlalchemy.ext.asyncio import AsyncSession

from fb.domain.friend.entities import FriendRequest, Friendship
from fb.domain.friend.value_objects import FriendRequestStatus
from fb.domain.shared.entity_id import EntityId
from fb.infrastructure.database.models.friend import FriendRequestModel, FriendshipModel


class SqlAlchemyFriendRepository:
    """SQLAlchemy implementation of FriendRepository protocol."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_request(
        self, sender_id: EntityId, receiver_id: EntityId
    ) -> FriendRequest | None:
        result = await self._session.execute(
            select(FriendRequestModel).where(
                and_(
                    FriendRequestModel.sender_id == sender_id.value,
                    FriendRequestModel.receiver_id == receiver_id.value,
                )
            )
        )
        model = result.scalar_one_or_none()
        return self._to_request_entity(model) if model else None

    async def find_request_by_id(
        self, request_id: EntityId
    ) -> FriendRequest | None:
        result = await self._session.execute(
            select(FriendRequestModel).where(
                FriendRequestModel.id == request_id.value
            )
        )
        model = result.scalar_one_or_none()
        return self._to_request_entity(model) if model else None

    async def save_request(self, request: FriendRequest) -> FriendRequest:
        model = FriendRequestModel(
            sender_id=request.sender_id.value,
            receiver_id=request.receiver_id.value,
        )
        model.id = request.id.value
        model.status = request.status.value
        self._session.add(model)
        await self._session.flush()
        return self._to_request_entity(model)

    async def update_request(self, request: FriendRequest) -> FriendRequest:
        result = await self._session.execute(
            select(FriendRequestModel).where(
                FriendRequestModel.id == request.id.value
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise ValueError(f"FriendRequest {request.id} not found")
        model.status = request.status.value
        await self._session.flush()
        return self._to_request_entity(model)

    async def save_friendship(self, friendship: Friendship) -> Friendship:
        model = FriendshipModel(
            user_id=friendship.user_id.value,
            friend_id=friendship.friend_id.value,
        )
        model.id = friendship.id.value
        self._session.add(model)
        await self._session.flush()
        return self._to_friendship_entity(model)

    async def delete_friendship(
        self, user_id: EntityId, friend_id: EntityId
    ) -> None:
        await self._session.execute(
            delete(FriendshipModel).where(
                (
                    (FriendshipModel.user_id == user_id.value)
                    & (FriendshipModel.friend_id == friend_id.value)
                )
                | (
                    (FriendshipModel.user_id == friend_id.value)
                    & (FriendshipModel.friend_id == user_id.value)
                )
            )
        )
        await self._session.flush()

    async def are_friends(
        self, user_id: EntityId, friend_id: EntityId
    ) -> bool:
        result = await self._session.execute(
            select(FriendshipModel.id)
            .where(
                and_(
                    FriendshipModel.user_id == user_id.value,
                    FriendshipModel.friend_id == friend_id.value,
                )
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def get_friends(
        self, user_id: EntityId, limit: int = 20, offset: int = 0
    ) -> list[EntityId]:
        # Single query — no N+1; uses ix_friendship_user_id index on FriendshipModel.
        result = await self._session.execute(
            select(FriendshipModel.friend_id)
            .where(FriendshipModel.user_id == user_id.value)
            .limit(limit)
            .offset(offset)
        )
        return [EntityId(row) for row in result.scalars().all()]

    async def get_pending_requests(
        self, user_id: EntityId
    ) -> list[FriendRequest]:
        result = await self._session.execute(
            select(FriendRequestModel).where(
                and_(
                    FriendRequestModel.receiver_id == user_id.value,
                    FriendRequestModel.status == FriendRequestStatus.PENDING.value,
                )
            )
        )
        return [self._to_request_entity(m) for m in result.scalars().all()]

    async def get_mutual_friends(
        self, user_id: EntityId, other_id: EntityId
    ) -> list[EntityId]:
        user_friends = (
            select(FriendshipModel.friend_id)
            .where(FriendshipModel.user_id == user_id.value)
            .subquery()
        )
        other_friends = (
            select(FriendshipModel.friend_id)
            .where(FriendshipModel.user_id == other_id.value)
            .subquery()
        )
        result = await self._session.execute(
            select(user_friends.c.friend_id).where(
                user_friends.c.friend_id.in_(select(other_friends.c.friend_id))
            )
        )
        return [EntityId(row) for row in result.scalars().all()]

    async def get_friends_with_count(
        self, user_id: EntityId, limit: int = 20, offset: int = 0
    ) -> tuple[list[EntityId], int]:
        """Get paginated friends and total count in a single query using window function."""
        total_expr = over(func.count(), partition_by=None)
        stmt = (
            select(FriendshipModel.friend_id, total_expr.label("total"))
            .where(FriendshipModel.user_id == user_id.value)
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        rows = result.all()
        if not rows:
            return [], 0
        friend_ids = [EntityId(row[0]) for row in rows]
        total_count = rows[0][1]
        return friend_ids, total_count

    async def get_friend_count(self, user_id: EntityId) -> int:
        # Single query — no N+1; COUNT(*) with WHERE on indexed user_id column.
        result = await self._session.execute(
            select(func.count())
            .select_from(FriendshipModel)
            .where(FriendshipModel.user_id == user_id.value)
        )
        return result.scalar_one()

    @staticmethod
    def _to_request_entity(model: FriendRequestModel) -> FriendRequest:
        return FriendRequest(
            id=EntityId(model.id),
            sender_id=EntityId(model.sender_id),
            receiver_id=EntityId(model.receiver_id),
            status=FriendRequestStatus(model.status),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _to_friendship_entity(model: FriendshipModel) -> Friendship:
        return Friendship(
            id=EntityId(model.id),
            user_id=EntityId(model.user_id),
            friend_id=EntityId(model.friend_id),
            created_at=model.created_at,
        )
