from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, JSONResponse

from app.core.config import Settings, get_settings
from app.core.db.client import get_db
from app.features.import_.errors import ImportDomainError, InvalidInputError
from app.features.import_.repository import VideoRepository
from app.features.import_.schemas import UrlImportRequest, VideoStatus
from app.features.import_.service import (
    delete_video,
    import_from_url,
    import_uploaded_file,
    list_videos,
)
from app.features.import_.tasks import run_youtube_import

router = APIRouter(prefix="/videos", tags=["videos"])
media_router = APIRouter(prefix="/media", tags=["media"])


@media_router.get(
    "/thumbnails/{filename}",
    responses={404: {"description": "Thumbnail filename invalid or not on disk"}},
)
async def serve_thumbnail(
    filename: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=404, detail="not found")
    path = settings.thumbnails_dir / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(path, media_type="image/jpeg")


def get_video_repository() -> VideoRepository:
    return VideoRepository(get_db())


async def _file_chunks(upload: UploadFile, chunk_size: int = 1024 * 1024) -> AsyncIterator[bytes]:
    while chunk := await upload.read(chunk_size):
        yield chunk


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_video(
    file: Annotated[UploadFile, File()],
    repo: Annotated[VideoRepository, Depends(get_video_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if not file.filename:
        raise InvalidInputError("no file provided")

    doc = await import_uploaded_file(
        filename=file.filename,
        chunks=_file_chunks(file),
        repo=repo,
        settings=settings,
    )
    return {"data": doc.model_dump(mode="json", by_alias=True), "error": None}


@router.post("/download-url", status_code=status.HTTP_202_ACCEPTED)
async def download_from_url(
    request: UrlImportRequest,
    background: BackgroundTasks,
    repo: Annotated[VideoRepository, Depends(get_video_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    url = str(request.url)
    placeholder = await import_from_url(url=url, repo=repo, settings=settings)
    background.add_task(run_youtube_import, placeholder.id, url, repo=repo, settings=settings)
    return {"data": placeholder.model_dump(mode="json", by_alias=True), "error": None}


@router.get("")
async def list_all(
    repo: Annotated[VideoRepository, Depends(get_video_repository)],
    status: VideoStatus | None = None,
) -> dict[str, Any]:
    docs = await list_videos(repo=repo, status=status)
    return {
        "data": {"videos": [d.model_dump(mode="json", by_alias=True) for d in docs]},
        "error": None,
    }


@router.delete("/{video_id}")
async def delete_one(
    video_id: str,
    repo: Annotated[VideoRepository, Depends(get_video_repository)],
) -> dict[str, Any]:
    await delete_video(video_id=video_id, repo=repo)
    return {"data": {"id": video_id, "deleted": True}, "error": None}


def _import_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ImportDomainError)
    return JSONResponse(
        status_code=exc.http_status,
        content={"data": None, "error": {"code": exc.code, "message": str(exc)}},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ImportDomainError, _import_error_handler)
