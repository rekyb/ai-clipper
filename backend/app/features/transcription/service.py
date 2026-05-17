from app.features.import_.repository import VideoRepository
from app.features.transcription import coordinator
from app.features.transcription.errors import TranscriptNotFoundError
from app.features.transcription.repository import TranscriptRepository
from app.features.transcription.schemas import RetryResponse, TranscriptDocument


async def retry_transcription(video_id: str, *, repo: VideoRepository) -> RetryResponse:
    doc = await coordinator.retry(video_id, repo=repo)
    return RetryResponse(id=doc.id, status=doc.status)


async def get_transcript(
    video_id: str, *, transcript_repo: TranscriptRepository
) -> TranscriptDocument:
    doc = await transcript_repo.get_by_video_id(video_id)
    if doc is None:
        raise TranscriptNotFoundError(f"transcript for video {video_id} not found")
    return doc
