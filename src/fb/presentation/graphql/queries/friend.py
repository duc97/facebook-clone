from __future__ import annotations

import strawberry

from fb.application.friend.dtos import MutualFriendsInput as MutualDTO
from fb.application.friend.mutual_friends import MutualFriendsUseCase
from fb.domain.shared.entity_id import EntityId
from fb.infrastructure.repositories.friend_repo import SqlAlchemyFriendRepository
from fb.presentation.graphql.context import GraphQLContext
from fb.presentation.graphql.types.friend import FriendListType, FriendRequestType


@strawberry.type
class FriendQuery:
    @strawberry.field
    async def friends(
        self, info: strawberry.types.Info, user_id: strawberry.ID
    ) -> FriendListType:
        ctx: GraphQLContext = info.context
        container = ctx.container

        async with container.session_factory() as session:
            friend_repo = SqlAlchemyFriendRepository(session)
            uid = EntityId.from_str(str(user_id))
            friend_ids = await friend_repo.get_friends(uid)
            total_count = await friend_repo.get_friend_count(uid)

        return FriendListType(
            friend_ids=[str(fid) for fid in friend_ids],
            total_count=total_count,
        )

    @strawberry.field
    async def pending_requests(
        self, info: strawberry.types.Info
    ) -> list[FriendRequestType] | None:
        ctx: GraphQLContext = info.context
        if not ctx.is_authenticated:
            return None

        container = ctx.container

        async with container.session_factory() as session:
            friend_repo = SqlAlchemyFriendRepository(session)
            uid = EntityId.from_str(ctx.current_user_id)  # type: ignore[arg-type]
            requests = await friend_repo.get_pending_requests(uid)

        return [
            FriendRequestType(
                id=strawberry.ID(str(req.id)),
                sender_id=str(req.sender_id),
                receiver_id=str(req.receiver_id),
                status=req.status.value,
            )
            for req in requests
        ]

    @strawberry.field
    async def mutual_friends(
        self, info: strawberry.types.Info, other_id: strawberry.ID
    ) -> FriendListType | None:
        ctx: GraphQLContext = info.context
        if not ctx.is_authenticated:
            return None

        container = ctx.container

        async with container.session_factory() as session:
            friend_repo = SqlAlchemyFriendRepository(session)
            use_case = MutualFriendsUseCase(friend_repo)
            result = await use_case.execute(
                MutualDTO(
                    user_id=ctx.current_user_id,  # type: ignore[arg-type]
                    other_id=str(other_id),
                )
            )

        return FriendListType(
            friend_ids=result.friend_ids,
            total_count=result.total_count,
        )
