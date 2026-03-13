"""Post-upload processing pipeline — fire-and-forget."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fb.container import Container

logger = logging.getLogger(__name__)


async def trigger_image_processing(
    container: "Container",
    media_id: str,
    image_data: bytes,
    content_type: str,
) -> None:
    """Background: process image after upload."""
    from fb.application.media.process_image import ProcessImageInput, ProcessImageUseCase
    from fb.infrastructure.repositories.media_repo import SqlAlchemyMediaRepository

    try:
        # Use a new session (separate from upload transaction)
        async with container.session_factory() as session:
            media_repo = SqlAlchemyMediaRepository(session)
            use_case = ProcessImageUseCase(
                media_repo=media_repo,
                file_storage=container.file_storage,
            )
            await use_case.execute(ProcessImageInput(
                media_id=media_id,
                image_data=image_data,
                content_type=content_type,
            ))
            await session.commit()
    except Exception:
        logger.exception("Background image processing failed for media_id=%s", media_id)


def schedule_image_processing(
    container: "Container",
    media_id: str,
    image_data: bytes,
    content_type: str,
) -> None:
    """Schedule image processing as asyncio background task."""
    asyncio.create_task(
        trigger_image_processing(container, media_id, image_data, content_type)
    )


async def trigger_video_processing(
    container: "Container",
    media_id: str,
    video_data: bytes,
    content_type: str,
) -> None:
    """Background: process video after upload."""
    from fb.application.media.process_video import ProcessVideoInput, ProcessVideoUseCase
    from fb.infrastructure.repositories.media_repo import SqlAlchemyMediaRepository

    try:
        async with container.session_factory() as session:
            media_repo = SqlAlchemyMediaRepository(session)
            use_case = ProcessVideoUseCase(
                media_repo=media_repo,
                file_storage=container.file_storage,
            )
            await use_case.execute(
                ProcessVideoInput(
                    media_id=media_id,
                    video_data=video_data,
                    content_type=content_type,
                )
            )
            await session.commit()
    except Exception:
        logger.exception("Background video processing failed for media_id=%s", media_id)


def schedule_video_processing(
    container: "Container",
    media_id: str,
    video_data: bytes,
    content_type: str,
) -> None:
    """Schedule video processing as asyncio background task."""
    asyncio.create_task(
        trigger_video_processing(container, media_id, video_data, content_type)
    )
