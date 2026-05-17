from datetime import UTC, datetime

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.schemas.video_status import VideoStatus
from app.features.import_.repository import VideoRepository
from app.features.import_.schemas import VideoDocument, VideoSource
from app.features.transcription import coordinator
from app.features.transcription.errors import (
    InvalidTranscriptionTransitionError,
    TranscriptNotFoundError,
)


def _make_doc(*, status: VideoStatus, filename: str = "x.mp4") -> VideoDocument:
    now = datetime.now(UTC)
    return VideoDocument(
        id=str(ObjectId()),
        filename=filename,
        title=filename,
        source=VideoSource.UPLOAD,
        source_url=None,
        storage_path=f"/x/{filename}",
        thumbnail_path=None,
        duration_sec=10.0,
        file_size_bytes=1,
        container="mp4",
        content_hash=f"hash-{filename}",
        status=status,
        error_code=None,
        error_message=None,
        created_at=now,
        updated_at=now,
    )


async def test_enqueue_flips_imported_to_queued(test_db: AsyncIOMotorDatabase) -> None:
    repo = VideoRepository(test_db)
    inserted = await repo.insert(_make_doc(status=VideoStatus.IMPORTED))
    await coordinator.enqueue(inserted.id, repo=repo)
    fetched = await repo.get_by_id(inserted.id)
    assert fetched is not None
    assert fetched.status is VideoStatus.QUEUED


async def test_enqueue_is_noop_when_already_queued(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    inserted = await repo.insert(_make_doc(status=VideoStatus.QUEUED))
    await coordinator.enqueue(inserted.id, repo=repo)
    fetched = await repo.get_by_id(inserted.id)
    assert fetched is not None
    assert fetched.status is VideoStatus.QUEUED


async def test_enqueue_is_noop_when_already_transcribing(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    inserted = await repo.insert(_make_doc(status=VideoStatus.TRANSCRIBING))
    await coordinator.enqueue(inserted.id, repo=repo)
    fetched = await repo.get_by_id(inserted.id)
    assert fetched is not None
    assert fetched.status is VideoStatus.TRANSCRIBING


async def test_retry_flips_failed_to_queued_and_clears_error(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    doc = _make_doc(status=VideoStatus.FAILED)
    doc = doc.model_copy(update={"error_code": "AUDIO_DECODE_FAILED", "error_message": "x"})
    inserted = await repo.insert(doc)
    result = await coordinator.retry(inserted.id, repo=repo)
    assert result.status is VideoStatus.QUEUED
    fetched = await repo.get_by_id(inserted.id)
    assert fetched is not None
    assert fetched.error_code is None
    assert fetched.error_message is None


async def test_retry_returns_current_state_when_already_queued(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    inserted = await repo.insert(_make_doc(status=VideoStatus.QUEUED))
    result = await coordinator.retry(inserted.id, repo=repo)
    assert result.status is VideoStatus.QUEUED


async def test_retry_returns_current_state_when_already_transcribing(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    inserted = await repo.insert(_make_doc(status=VideoStatus.TRANSCRIBING))
    result = await coordinator.retry(inserted.id, repo=repo)
    assert result.status is VideoStatus.TRANSCRIBING


async def test_retry_returns_current_state_when_already_ready(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    inserted = await repo.insert(_make_doc(status=VideoStatus.READY))
    result = await coordinator.retry(inserted.id, repo=repo)
    assert result.status is VideoStatus.READY


async def test_retry_raises_invalid_transition_when_uploading(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    inserted = await repo.insert(_make_doc(status=VideoStatus.UPLOADING))
    try:
        await coordinator.retry(inserted.id, repo=repo)
    except InvalidTranscriptionTransitionError as exc:
        assert "uploading" in str(exc).lower()
    else:
        raise AssertionError("expected InvalidTranscriptionTransitionError")


async def test_retry_raises_not_found_when_missing(test_db: AsyncIOMotorDatabase) -> None:
    repo = VideoRepository(test_db)
    try:
        await coordinator.retry(str(ObjectId()), repo=repo)
    except TranscriptNotFoundError:
        pass
    else:
        raise AssertionError("expected TranscriptNotFoundError")


async def test_retry_youtube_import_resets_failed_to_uploading_and_clears_error(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    doc = _make_doc(status=VideoStatus.FAILED)
    doc = doc.model_copy(
        update={
            "source": VideoSource.YOUTUBE,
            "source_url": "https://youtu.be/x",
            "storage_path": "",
            "error_code": "VIDEO_AUTH_REQUIRED",
            "error_message": "bot check",
        }
    )
    inserted = await repo.insert(doc)
    result = await coordinator.retry_youtube_import(inserted.id, repo=repo)
    assert result.status is VideoStatus.UPLOADING
    fetched = await repo.get_by_id(inserted.id)
    assert fetched is not None
    assert fetched.error_code is None
    assert fetched.error_message is None
    assert fetched.source is VideoSource.YOUTUBE
    assert fetched.source_url == "https://youtu.be/x"


async def test_retry_youtube_import_raises_when_not_failed(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    doc = _make_doc(status=VideoStatus.READY).model_copy(
        update={"source": VideoSource.YOUTUBE, "source_url": "https://youtu.be/x"}
    )
    inserted = await repo.insert(doc)
    try:
        await coordinator.retry_youtube_import(inserted.id, repo=repo)
    except InvalidTranscriptionTransitionError:
        pass
    else:
        raise AssertionError("expected InvalidTranscriptionTransitionError")


async def test_retry_youtube_import_raises_when_source_not_youtube(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    doc = _make_doc(status=VideoStatus.FAILED).model_copy(
        update={"source": VideoSource.UPLOAD, "storage_path": "", "error_code": "X"}
    )
    inserted = await repo.insert(doc)
    try:
        await coordinator.retry_youtube_import(inserted.id, repo=repo)
    except InvalidTranscriptionTransitionError:
        pass
    else:
        raise AssertionError("expected InvalidTranscriptionTransitionError")


async def test_retry_youtube_import_raises_not_found_when_missing(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    try:
        await coordinator.retry_youtube_import(str(ObjectId()), repo=repo)
    except TranscriptNotFoundError:
        pass
    else:
        raise AssertionError("expected TranscriptNotFoundError")


async def test_back_fill_at_startup_sweeps_transcribing_and_back_fills_imported(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    transcribing = await repo.insert(_make_doc(status=VideoStatus.TRANSCRIBING, filename="t.mp4"))
    imported = await repo.insert(_make_doc(status=VideoStatus.IMPORTED, filename="i.mp4"))
    await repo.insert(_make_doc(status=VideoStatus.READY, filename="r.mp4"))

    count = await coordinator.back_fill_at_startup(repo=repo)
    assert count == 2

    for vid in (transcribing.id, imported.id):
        fetched = await repo.get_by_id(vid)
        assert fetched is not None
        assert fetched.status is VideoStatus.QUEUED


async def test_back_fill_at_startup_zero_when_empty(test_db: AsyncIOMotorDatabase) -> None:
    repo = VideoRepository(test_db)
    await repo.insert(_make_doc(status=VideoStatus.READY))
    count = await coordinator.back_fill_at_startup(repo=repo)
    assert count == 0
