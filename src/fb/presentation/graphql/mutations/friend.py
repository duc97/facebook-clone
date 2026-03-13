from __future__ import annotations

import strawberry

from fb.application.friend.accept_request import AcceptRequestUseCase
from fb.application.friend.dtos import (
    AcceptRequestInput as AcceptDTO,
    RejectRequestInput as RejectDTO,
    SendRequestInput as SendDTO,
    UnfriendInput as UnfriendDTO,
)
from fb.application.friend.reject_request import RejectRequestUseCase
from fb.application.friend.send_request import SendRequestUseCase
from fb.application.friend.unfriend import UnfriendUseCase
from fb.infrastructure.repositories.friend_repo import SqlAlchemyFriendRepository
from fb.presentation.graphql.context import GraphQLContext
from fb.presentation.graphql.types.auth import MessageResponse
from fb.presentation.graphql.types.friend import FriendRequestType


@strawberry.type
class FriendMutation:
    @strawberry.mutation
    async def send_friend_request(
        self, info: strawberry.types.Info, receiver_id: strawberry.ID
    ) -> FriendRequestType | None:
        ctx: GraphQLContext = info.context
        if not ctx.is_authenticated:
            return None

        container = ctx.container
        uow = container.create_uow()
        async with uow:
            friend_repo = SqlAlchemyFriendRepository(uow.session)
            use_case = SendRequestUseCase(friend_repo=friend_repo, uow=uow)

            result = await use_case.execute(
                SendDTO(
                    sender_id=ctx.current_user_id,  # type: ignore[arg-type]
                    receiver_id=str(receiver_id),
                )
            )

        return FriendRequestType(
            id=strawberry.ID(result.id),
            sender_id=result.sender_id,
            receiver_id=result.receiver_id,
            status=result.status,
        )

    @strawberry.mutation
    async def accept_friend_request(
        self, info: strawberry.types.Info, request_id: strawberry.ID
    ) -> FriendRequestType | None:
        ctx: GraphQLContext = info.context
        if not ctx.is_authenticated:
            return None

        container = ctx.container
        uow = container.create_uow()
        async with uow:
            friend_repo = SqlAlchemyFriendRepository(uow.session)
            use_case = AcceptRequestUseCase(friend_repo=friend_repo, uow=uow)

            result = await use_case.execute(
                AcceptDTO(
                    request_id=str(request_id),
                    user_id=ctx.current_user_id,  # type: ignore[arg-type]
                )
            )

        return FriendRequestType(
            id=strawberry.ID(result.id),
            sender_id=result.sender_id,
            receiver_id=result.receiver_id,
            status=result.status,
        )

    @strawberry.mutation
    async def reject_friend_request(
        self, info: strawberry.types.Info, request_id: strawberry.ID
    ) -> MessageResponse | None:
        ctx: GraphQLContext = info.context
        if not ctx.is_authenticated:
            return None

        container = ctx.container
        uow = container.create_uow()
        async with uow:
            friend_repo = SqlAlchemyFriendRepository(uow.session)
            use_case = RejectRequestUseCase(friend_repo=friend_repo, uow=uow)

            await use_case.execute(
                RejectDTO(
                    request_id=str(request_id),
                    user_id=ctx.current_user_id,  # type: ignore[arg-type]
                )
            )

        return MessageResponse(message="Friend request rejected", success=True)

    @strawberry.mutation
    async def unfriend(
        self, info: strawberry.types.Info, friend_id: strawberry.ID
    ) -> MessageResponse | None:
        ctx: GraphQLContext = info.context
        if not ctx.is_authenticated:
            return None

        container = ctx.container
        uow = container.create_uow()
        async with uow:
            friend_repo = SqlAlchemyFriendRepository(uow.session)
            use_case = UnfriendUseCase(friend_repo=friend_repo, uow=uow)

            await use_case.execute(
                UnfriendDTO(
                    user_id=ctx.current_user_id,  # type: ignore[arg-type]
                    friend_id=str(friend_id),
                )
            )

        return MessageResponse(message="Unfriended successfully", success=True)
