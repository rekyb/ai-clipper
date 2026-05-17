from app.core.schemas.video_status import VideoStatus
from app.features.import_.repository import VideoRepository
from app.features.import_.schemas import VideoDocument, VideoSource
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


async def retry_youtube_import(video_id: str, *, repo: VideoRepository) -> VideoDocument:
    # For YouTube imports that died before producing a file (typical causes:
    # auth wall, format unavailable). Resets the record so the route handler
    # can re-trigger run_youtube_import.
    existing = await repo.get_by_id(video_id)
    if existing is None:
        raise TranscriptNotFoundError(f"video {video_id} not found")
    if existing.status is not VideoStatus.FAILED:
        raise InvalidTranscriptionTransitionError(
            f"can only retry youtube import on a failed video; got '{existing.status.value}'"
        )
    if existing.source is not VideoSource.YOUTUBE or not existing.source_url:
        raise InvalidTranscriptionTransitionError(
            "youtube import retry requires source=youtube and a stored source_url"
        )
    updated = await repo.transition_status(
        video_id,
        from_status=VideoStatus.FAILED,
        to_status=VideoStatus.UPLOADING,
        clear_error=True,
    )
    if updated is None:
        current = await repo.get_by_id(video_id)
        if current is None:
            raise TranscriptNotFoundError(f"video {video_id} not found")
        return current
    return updated


async def back_fill_at_startup(*, repo: VideoRepository) -> int:
    swept = await repo.sweep_stale_transcribing()
    bfilled = await repo.back_fill_imported()
    return len(swept) + len(bfilled)
