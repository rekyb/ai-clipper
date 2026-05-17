from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.db.client import get_db
from app.features.import_.repository import VideoRepository
from app.features.transcription.errors import TranscriptionDomainError
from app.features.transcription.repository import TranscriptRepository
from app.features.transcription.service import get_transcript, retry_transcription

router = APIRouter(prefix="/videos", tags=["transcription"])


def get_video_repository() -> VideoRepository:
    return VideoRepository(get_db())


def get_transcript_repository() -> TranscriptRepository:
    return TranscriptRepository(get_db())


@router.post("/{video_id}/retry")
async def retry_video(
    video_id: str,
    repo: Annotated[VideoRepository, Depends(get_video_repository)],
) -> dict[str, Any]:
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
