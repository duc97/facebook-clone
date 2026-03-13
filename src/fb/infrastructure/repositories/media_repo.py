from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from fb.domain.media.entities import Media, MediaStatus, MediaType
from fb.domain.shared.entity_id import EntityId
from fb.infrastructure.database.models.media import MediaModel


class SqlAlchemyMediaRepository:
    """SQLAlchemy implementation of MediaRepository protocol."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, media: Media) -> Media:
        """Persist a Media entity (insert or upsert via merge)."""
        model = MediaModel(
            owner_id=media.owner_id.value,
            entity_id=media.entity_id,
            entity_type=media.entity_type,
            original_url=media.original_url,
            thumbnail_url=media.thumbnail_url,
            processed_url=media.processed_url,
            media_type=media.media_type.value,
            content_type=media.content_type,
            file_size=media.file_size,
            width=media.width,
            height=media.height,
            duration_seconds=media.duration_seconds,
        )
        model.id = media.id.value
        model.status = media.status.value
        model = await self._session.merge(model)
        await self._session.flush()
        return self._to_entity(model)

    # Alias kept for backward-compat with use cases written before protocol change
    async def add(self, media: Media) -> Media:
        return await self.save(media)

    async def find_by_id(self, media_id: EntityId) -> Media | None:
        result = await self._session.execute(
            select(MediaModel).where(MediaModel.id == media_id.value)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_by_owner(
        self,
        owner_id: EntityId,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Media]:
        result = await self._session.execute(
            select(MediaModel)
            .where(MediaModel.owner_id == owner_id.value)
            .order_by(MediaModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def find_by_entity(self, entity_type: str, entity_id: str) -> list[Media]:
        """Return all media for a given entity (post, avatar, etc.), oldest first."""
        result = await self._session.execute(
            select(MediaModel)
            .where(
                MediaModel.entity_type == entity_type,
                MediaModel.entity_id == entity_id,
            )
            .order_by(MediaModel.created_at.asc())
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def update_status(
        self,
        media_id: EntityId,
        status: MediaStatus,
        processed_url: str | None = None,
        thumbnail_url: str | None = None,
        width: int | None = None,
        height: int | None = None,
        duration_seconds: float | None = None,
    ) -> None:
        values: dict = {"status": status.value}
        if processed_url is not None:
            values["processed_url"] = processed_url
        if thumbnail_url is not None:
            values["thumbnail_url"] = thumbnail_url
        if width is not None:
            values["width"] = width
        if height is not None:
            values["height"] = height
        if duration_seconds is not None:
            values["duration_seconds"] = duration_seconds

        stmt = (
            update(MediaModel)
            .where(MediaModel.id == media_id.value)
            .values(**values)
        )
        await self._session.execute(stmt)

    async def delete(self, media_id: EntityId) -> None:
        result = await self._session.execute(
            select(MediaModel).where(MediaModel.id == media_id.value)
        )
        model = result.scalar_one_or_none()
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()

    @staticmethod
    def _to_entity(model: MediaModel) -> Media:
        # updated_at is optional on the model (may not exist in older schema versions)
        updated_at = getattr(model, "updated_at", None)
        return Media(
            id=EntityId.from_str(str(model.id)),
            owner_id=EntityId.from_str(str(model.owner_id)),
            entity_id=model.entity_id,
            entity_type=model.entity_type,
            original_url=model.original_url,
            thumbnail_url=model.thumbnail_url,
            processed_url=model.processed_url,
            media_type=MediaType(model.media_type),
            content_type=model.content_type,
            file_size=model.file_size,
            width=model.width,
            height=model.height,
            duration_seconds=model.duration_seconds,
            status=MediaStatus(model.status),
            created_at=model.created_at,
            updated_at=updated_at,
        )
