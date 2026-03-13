from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from fastapi.responses import Response as FR

from fb.application.media.delete_media import DeleteMediaUseCase
from fb.application.media.dtos import DeleteMediaInput, UploadInput
from fb.application.media.get_media import GetEntityMediaUseCase, GetMediaUseCase
from fb.application.media.upload import UploadUseCase
from fb.container import Container
from fb.infrastructure.repositories.media_repo import SqlAlchemyMediaRepository
from fb.presentation.dependencies import get_container, get_current_user_id
from fb.presentation.rest.response import success_response

router = APIRouter(tags=["media"])


@router.post("/media/upload", status_code=201)
async def upload_media(
    entity_type: str = Query(..., description="post|avatar|cover|chat"),
    entity_id: str = Query(default=""),
    file: UploadFile = File(...),
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> Response:
    """Upload a media file (image or video)."""
    file_data = await file.read()
    uow = container.create_uow()
    async with uow:
        media_repo = SqlAlchemyMediaRepository(uow.session)
        use_case = UploadUseCase(
            media_repo=media_repo,
            file_storage=container.file_storage,
            uow=uow,
        )
        result = await use_case.execute(
            UploadInput(
                owner_id=current_user_id,
                entity_id=entity_id,
                entity_type=entity_type,
                file_data=file_data,
                filename=file.filename or "upload",
                content_type=file.content_type or "application/octet-stream",
            )
        )
    return success_response(result.__dict__, status_code=201)


@router.get("/media/{media_id}")
async def get_media(
    media_id: str,
    container: Container = Depends(get_container),
) -> Response:
    """Retrieve a single media record by ID."""
    async with container.session_factory() as session:
        media_repo = SqlAlchemyMediaRepository(session)
        use_case = GetMediaUseCase(media_repo=media_repo)
        result = await use_case.execute(media_id)
    return success_response(result.__dict__)


@router.get("/media")
async def list_media(
    entity_type: str = Query(...),
    entity_id: str = Query(...),
    container: Container = Depends(get_container),
) -> Response:
    """List all media attached to a given entity (e.g. post, avatar)."""
    async with container.session_factory() as session:
        media_repo = SqlAlchemyMediaRepository(session)
        use_case = GetEntityMediaUseCase(media_repo=media_repo)
        results = await use_case.execute(entity_type=entity_type, entity_id=entity_id)
    return success_response([r.__dict__ for r in results])


@router.delete("/media/{media_id}", status_code=204)
async def delete_media(
    media_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> Response:
    """Delete a media record. Only the owner may delete."""
    uow = container.create_uow()
    async with uow:
        media_repo = SqlAlchemyMediaRepository(uow.session)
        use_case = DeleteMediaUseCase(
            media_repo=media_repo,
            file_storage=container.file_storage,
            uow=uow,
        )
        await use_case.execute(DeleteMediaInput(media_id=media_id, owner_id=current_user_id))
    return FR(status_code=204)


@router.get("/media/{media_id}/presigned-url")
async def get_presigned_url(
    media_id: str,
    expires_in: int = Query(default=3600, ge=60, le=86400),
    current_user_id: str = Depends(get_current_user_id),
    container: Container = Depends(get_container),
) -> Response:
    """Get a presigned URL for accessing private media."""
    from fastapi import HTTPException

    from fb.domain.shared.entity_id import EntityId

    async with container.session_factory() as session:
        media_repo = SqlAlchemyMediaRepository(session)
        media = await media_repo.find_by_id(EntityId.from_str(media_id))

    if media is None:
        raise HTTPException(status_code=404, detail="Media not found")

    url = media.processed_url or media.original_url
    presigned = await container.file_storage.generate_presigned_url(url, expires_in=expires_in)
    return success_response({"url": presigned, "expires_in": expires_in})
