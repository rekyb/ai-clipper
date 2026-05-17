from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.core.db.client import get_db
from app.core.schemas.video_status import VideoStatus
from app.features.import_.repository import VideoRepository
from app.features.import_.schemas import VideoSource
from app.features.import_.tasks import run_youtube_import
from app.features.transcription import coordinator
from app.features.transcription.errors import (
    TranscriptionDomainError,
    TranscriptNotFoundError,
)
from app.features.transcription.repository import TranscriptRepository
from app.features.transcription.schemas import RetryResponse
from app.features.transcription.service import get_transcript, retry_transcription

router = APIRouter(prefix="/videos", tags=["transcription"])


def get_video_repository() -> VideoRepository:
    return VideoRepository(get_db())


def get_transcript_repository() -> TranscriptRepository:
    return TranscriptRepository(get_db())


def _needs_youtube_import_retry(video: Any) -> bool:
    return (
        video.status is VideoStatus.FAILED
        and video.source is VideoSource.YOUTUBE
        and bool(video.source_url)
        and not video.storage_path
    )


@router.post("/{video_id}/retry")
async def retry_video(
    video_id: str,
    background: BackgroundTasks,
    repo: Annotated[VideoRepository, Depends(get_video_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    existing = await repo.get_by_id(video_id)
    if existing is None:
        raise TranscriptNotFoundError(f"video {video_id} not found")

    if _needs_youtube_import_retry(existing):
        reset = await coordinator.retry_youtube_import(video_id, repo=repo)
        # source_url is guaranteed by _needs_youtube_import_retry's check above
        assert existing.source_url is not None
        background.add_task(
            run_youtube_import, video_id, existing.source_url, repo=repo, settings=settings
        )
        result = RetryResponse(id=reset.id, status=reset.status)
    else:
        result = await retry_transcription(video_id, repo=repo)

    return {"data": result.model_dump(mode="json", by_alias=True), "error": None}


@router.get("/{video_id}/transcript")
async def get_video_transcript(
    video_id: str,
    transcript_repo: Annotated[TranscriptRepository, Depends(get_transcript_repository)],
) -> dict[str, Any]:
    doc = await get_transcript(video_id, transcript_repo=transcript_repo)
    return {"data": doc.model_dump(mode="json", by_alias=True), "error": None}


def _transcription_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, TranscriptionDomainError)
    return JSONResponse(
        status_code=exc.http_status,
        content={"data": None, "error": {"code": exc.code, "message": str(exc)}},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(TranscriptionDomainError, _transcription_error_handler)
