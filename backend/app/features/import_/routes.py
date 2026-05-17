from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, File, Request, UploadFile, status
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.core.db.client import get_db
from app.features.import_.errors import ImportDomainError, InvalidInputError
from app.features.import_.repository import VideoRepository
from app.features.import_.service import import_uploaded_file

router = APIRouter(prefix="/videos", tags=["videos"])


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
    return {"data": doc.model_dump(mode="json"), "error": None}


def _import_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ImportDomainError)
    return JSONResponse(
        status_code=exc.http_status,
        content={"data": None, "error": {"code": exc.code, "message": str(exc)}},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ImportDomainError, _import_error_handler)
