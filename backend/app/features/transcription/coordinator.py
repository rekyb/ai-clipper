from app.core.schemas.video_status import VideoStatus
from app.features.import_.repository import VideoRepository
from app.features.import_.schemas import VideoDocument
from app.features.transcription.errors import (
    InvalidTranscriptionTransitionError,
    TranscriptNotFoundError,
)

_IDEMPOTENT_RETRY_STATES = {
    VideoStatus.QUEUED,
    VideoStatus.TRANSCRIBING,
    VideoStatus.READY,
}


async def enqueue(video_id: str, *, repo: VideoRepository) -> None:
    await repo.transition_status(
        video_id,
        from_status=VideoStatus.IMPORTED,
        to_status=VideoStatus.QUEUED,
    )


async def retry(video_id: str, *, repo: VideoRepository) -> VideoDocument:
    existing = await repo.get_by_id(video_id)
    if existing is None:
        raise TranscriptNotFoundError(f"video {video_id} not found")
    if existing.status is VideoStatus.FAILED:
        updated = await repo.transition_status(
            video_id,
            from_status=VideoStatus.FAILED,
            to_status=VideoStatus.QUEUED,
            clear_error=True,
        )
        if updated is None:
            # Lost a race; re-read and return current state.
            current = await repo.get_by_id(video_id)
            if current is None:
                raise TranscriptNotFoundError(f"video {video_id} not found")
            return current
        return updated
    if existing.status in _IDEMPOTENT_RETRY_STATES:
        return existing
    raise InvalidTranscriptionTransitionError(
        f"cannot retry video in status '{existing.status.value}'"
    )


async def back_fill_at_startup(*, repo: VideoRepository) -> int:
    swept = await repo.sweep_stale_transcribing()
    bfilled = await repo.back_fill_imported()
    return len(swept) + len(bfilled)
