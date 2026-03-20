"""Request-scoped DataLoaders for the GraphQL layer.

Each DataLoader batches multiple individual lookups that arrive within the
same request tick into a single SQL IN-clause query, eliminating N+1.

Lifecycle: one ``GraphQLLoaders`` instance per request (created in
``get_graphql_context``), discarded when the request ends.  Never share
loader instances across requests — they are not thread/task-safe.

Usage in a resolver::

    ctx: GraphQLContext = info.context
    profile = await ctx.loaders.profile.load(user_id_str)
    post    = await ctx.loaders.post.load(post_id_str)
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from strawberry.dataloader import DataLoader

from fb.domain.post.entities import Post
from fb.domain.profile.entities import Profile
from fb.domain.shared.entity_id import EntityId
from fb.infrastructure.repositories.post_repo import SqlAlchemyPostRepository
from fb.infrastructure.repositories.profile_repo import SqlAlchemyProfileRepository

# ── Batch-load functions ─────────────────────────────────────────────────────

def _make_post_loader(
    session_factory: async_sessionmaker[AsyncSession],
) -> DataLoader[str, Post | None]:
    """Return a DataLoader that batch-fetches posts by string ID."""

    async def load_posts(post_ids: Sequence[str]) -> list[Post | None]:
        async with session_factory() as session:
            repo = SqlAlchemyPostRepository(session)
            entity_ids = [EntityId.from_str(pid) for pid in post_ids]
            return await repo.find_by_ids(entity_ids)

    return DataLoader(load_fn=load_posts)


def _make_profile_loader(
    session_factory: async_sessionmaker[AsyncSession],
) -> DataLoader[str, Profile | None]:
    """Return a DataLoader that batch-fetches profiles by user_id string."""

    async def load_profiles(user_ids: Sequence[str]) -> list[Profile | None]:
        async with session_factory() as session:
            repo = SqlAlchemyProfileRepository(session)
            entity_ids = [EntityId.from_str(uid) for uid in user_ids]
            return await repo.find_by_user_ids(entity_ids)

    return DataLoader(load_fn=load_profiles)


# ── Container ────────────────────────────────────────────────────────────────

@dataclass
class GraphQLLoaders:
    """Holds all request-scoped DataLoader instances."""

    post: DataLoader[str, Post | None]
    profile: DataLoader[str, Profile | None]

    @classmethod
    def for_request(
        cls, session_factory: async_sessionmaker[AsyncSession]
    ) -> GraphQLLoaders:
        """Create a fresh set of loaders for one GraphQL request."""
        return cls(
            post=_make_post_loader(session_factory),
            profile=_make_profile_loader(session_factory),
        )
