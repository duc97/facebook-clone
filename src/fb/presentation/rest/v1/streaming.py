"""Video streaming endpoint with range request support."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from fb.container import Container
from fb.presentation.dependencies import get_container

logger = logging.getLogger(__name__)
router = APIRouter(tags=["streaming"])


@router.get("/media/{media_id}/stream")
async def stream_video(
    media_id: str,
    request: Request,
    expires_in: int = Query(default=3600, ge=60, le=86400),
    container: Container = Depends(get_container),
) -> StreamingResponse:
    """Get a streaming URL (presigned) for a video media object.

    For S3 backend: returns redirect to presigned URL.
    For local backend: streams file with Range support.
    """
    from fb.domain.media.entities import MediaStatus, MediaType
    from fb.domain.shared.entity_id import EntityId
    from fb.infrastructure.repositories.media_repo import SqlAlchemyMediaRepository

    async with container.session_factory() as session:
        media_repo = SqlAlchemyMediaRepository(session)
        media = await media_repo.find_by_id(EntityId.from_str(media_id))

    if media is None:
        raise HTTPException(status_code=404, detail="Media not found")

    if media.media_type != MediaType.VIDEO:
        raise HTTPException(status_code=400, detail="Media is not a video")

    # Allow PENDING as well — original is already uploaded even if not processed
    if media.status == MediaStatus.FAILED:
        raise HTTPException(status_code=422, detail="Media processing failed")

    video_url = media.original_url  # use original (not processed) for video

    # S3 backend: redirect to presigned URL
    if container.settings.storage_backend == "s3":
        presigned = await container.file_storage.generate_presigned_url(
            video_url, expires_in=expires_in
        )
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=presigned, status_code=302)

    # Local backend: stream file with range support
    return await _stream_local_file(video_url, request, container)


async def _stream_local_file(
    file_url: str,
    request: Request,
    container: Container,
) -> StreamingResponse:
    """Stream a local file with HTTP Range support."""
    # file_url is like "/uploads/videos/uuid.mp4" or "/uploads/uuid.mp4"
    upload_dir = container.settings.upload_dir

    # Try to map the URL path to a filesystem path
    # Strip leading "/uploads/" prefix to get the relative path
    relative = file_url
    if relative.startswith("/uploads/"):
        relative = relative[len("/uploads/"):]
    elif relative.startswith("/"):
        relative = relative[1:]

    file_path = Path(upload_dir) / relative

    if not file_path.exists():
        # Fallback: flat lookup by filename only
        filename = file_url.rsplit("/", 1)[-1]
        file_path = Path(upload_dir) / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")

    file_size = file_path.stat().st_size

    # Determine content type from extension
    suffix = file_path.suffix.lower()
    content_type_map = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
    }
    content_type = content_type_map.get(suffix, "video/mp4")

    range_header = request.headers.get("range")

    if range_header:
        # Parse Range: bytes=start-end
        try:
            range_val = range_header.replace("bytes=", "").strip()
            parts = range_val.split("-")
            start = int(parts[0])
            end = int(parts[1]) if parts[1] else file_size - 1
        except (ValueError, IndexError):
            raise HTTPException(status_code=416, detail="Invalid Range header")

        if start >= file_size or end >= file_size or start > end:
            raise HTTPException(
                status_code=416,
                detail=f"Range not satisfiable: {range_header}",
            )

        end = min(end, file_size - 1)
        chunk_size = end - start + 1

        async def generate_range():  # type: ignore[return]
            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = chunk_size
                while remaining > 0:
                    read_size = min(65536, remaining)  # 64 KB chunks
                    data = f.read(read_size)
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        return StreamingResponse(
            generate_range(),
            status_code=206,
            media_type=content_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(chunk_size),
            },
        )

    # Full file stream
    async def generate_full():  # type: ignore[return]
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(65536)  # 64 KB chunks
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        generate_full(),
        status_code=200,
        media_type=content_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
        },
    )
