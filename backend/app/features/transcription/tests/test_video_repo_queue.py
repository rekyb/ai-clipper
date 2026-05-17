from datetime import UTC, datetime, timedelta

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.schemas.video_status import VideoStatus
from app.features.import_.repository import VideoRepository
from app.features.import_.schemas import VideoDocument, VideoSource


def _make_doc(
    *,
    status: VideoStatus = VideoStatus.IMPORTED,
    created_at: datetime | None = None,
    filename: str = "x.mp4",
    last_progress_percent: int | None = None,
) -> VideoDocument:
    now = created_at or datetime.now(UTC)
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
        last_progress_percent=last_progress_percent,
    )


async def test_transition_status_changes_status_when_precondition_matches(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    doc = await repo.insert(_make_doc(status=VideoStatus.IMPORTED))
    updated = await repo.transition_status(
        doc.id,
        from_status=VideoStatus.IMPORTED,
        to_status=VideoStatus.QUEUED,
    )
    assert updated is not None
    assert updated.status is VideoStatus.QUEUED


async def test_transition_status_returns_none_when_precondition_fails(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    doc = await repo.insert(_make_doc(status=VideoStatus.READY))
    updated = await repo.transition_status(
        doc.id,
        from_status=VideoStatus.IMPORTED,
        to_status=VideoStatus.QUEUED,
    )
    assert updated is None


async def test_transition_status_accepts_set_of_allowed_from_states(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    doc = await repo.insert(_make_doc(status=VideoStatus.FAILED))
    updated = await repo.transition_status(
        doc.id,
        from_status={VideoStatus.FAILED, VideoStatus.IMPORTED},
        to_status=VideoStatus.QUEUED,
    )
    assert updated is not None
    assert updated.status is VideoStatus.QUEUED


async def test_transition_status_sets_error_fields(test_db: AsyncIOMotorDatabase) -> None:
    repo = VideoRepository(test_db)
    doc = await repo.insert(_make_doc(status=VideoStatus.TRANSCRIBING))
    updated = await repo.transition_status(
        doc.id,
        from_status=VideoStatus.TRANSCRIBING,
        to_status=VideoStatus.FAILED,
        error_code="TRANSCRIPTION_FAILED",
        error_message="whisper exploded",
    )
    assert updated is not None
    assert updated.error_code == "TRANSCRIPTION_FAILED"
    assert updated.error_message == "whisper exploded"


async def test_transition_status_clears_error_when_explicitly_set_to_none(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    doc = await repo.insert(_make_doc(status=VideoStatus.FAILED))
    await repo.transition_status(
        doc.id,
        from_status=VideoStatus.FAILED,
        to_status=VideoStatus.QUEUED,
        clear_error=True,
    )
    fetched = await repo.get_by_id(doc.id)
    assert fetched is not None
    assert fetched.error_code is None
    assert fetched.error_message is None


async def test_claim_next_queued_returns_oldest_and_flips_to_transcribing(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    base = datetime(2026, 1, 1, tzinfo=UTC)
    await repo.insert(
        _make_doc(
            status=VideoStatus.QUEUED, created_at=base + timedelta(hours=2), filename="newest.mp4"
        )
    )
    await repo.insert(_make_doc(status=VideoStatus.QUEUED, created_at=base, filename="oldest.mp4"))
    await repo.insert(
        _make_doc(
            status=VideoStatus.QUEUED, created_at=base + timedelta(hours=1), filename="middle.mp4"
        )
    )

    claimed = await repo.claim_next_queued()
    assert claimed is not None
    assert claimed.filename == "oldest.mp4"
    assert claimed.status is VideoStatus.TRANSCRIBING


async def test_claim_next_queued_returns_none_when_queue_empty(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    await repo.insert(_make_doc(status=VideoStatus.READY))
    claimed = await repo.claim_next_queued()
    assert claimed is None


async def test_claim_next_queued_sets_transcription_started_at(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    await repo.insert(_make_doc(status=VideoStatus.QUEUED))
    before = datetime.now(UTC)
    claimed = await repo.claim_next_queued()
    after = datetime.now(UTC)
    assert claimed is not None
    assert claimed.transcription_started_at is not None
    # Mongo stores datetimes at millisecond precision; allow a 1ms slack on both ends.
    slack = timedelta(milliseconds=1)
    assert (before - slack) <= claimed.transcription_started_at <= (after + slack)


async def test_update_progress_persists_last_progress_percent(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    doc = await repo.insert(_make_doc(status=VideoStatus.TRANSCRIBING))
    await repo.update_progress(doc.id, percent=42)
    fetched = await repo.get_by_id(doc.id)
    assert fetched is not None
    assert fetched.last_progress_percent == 42


async def test_sweep_stale_transcribing_returns_them_to_queued(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    a = await repo.insert(
        _make_doc(status=VideoStatus.TRANSCRIBING, filename="a.mp4", last_progress_percent=30)
    )
    b = await repo.insert(_make_doc(status=VideoStatus.TRANSCRIBING, filename="b.mp4"))
    await repo.insert(_make_doc(status=VideoStatus.READY, filename="c.mp4"))

    swept_ids = await repo.sweep_stale_transcribing()
    assert set(swept_ids) == {a.id, b.id}

    for vid in (a.id, b.id):
        fetched = await repo.get_by_id(vid)
        assert fetched is not None
        assert fetched.status is VideoStatus.QUEUED
        assert fetched.restarted_at is not None

    a_after = await repo.get_by_id(a.id)
    assert a_after is not None
    assert a_after.last_progress_percent == 30


async def test_back_fill_imported_flips_to_queued(test_db: AsyncIOMotorDatabase) -> None:
    repo = VideoRepository(test_db)
    a = await repo.insert(_make_doc(status=VideoStatus.IMPORTED, filename="a.mp4"))
    b = await repo.insert(_make_doc(status=VideoStatus.IMPORTED, filename="b.mp4"))
    await repo.insert(_make_doc(status=VideoStatus.READY, filename="c.mp4"))

    filled = await repo.back_fill_imported()
    assert set(filled) == {a.id, b.id}

    for vid in (a.id, b.id):
        fetched = await repo.get_by_id(vid)
        assert fetched is not None
        assert fetched.status is VideoStatus.QUEUED


async def test_count_queued_before_returns_zero_for_oldest(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    base = datetime(2026, 1, 1, tzinfo=UTC)
    oldest = await repo.insert(
        _make_doc(status=VideoStatus.QUEUED, created_at=base, filename="a.mp4")
    )
    await repo.insert(
        _make_doc(status=VideoStatus.QUEUED, created_at=base + timedelta(hours=1), filename="b.mp4")
    )

    count = await repo.count_queued_before(oldest.id)
    assert count == 0


async def test_count_queued_before_counts_earlier_queued_videos(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    base = datetime(2026, 1, 1, tzinfo=UTC)
    await repo.insert(_make_doc(status=VideoStatus.QUEUED, created_at=base, filename="a.mp4"))
    await repo.insert(
        _make_doc(status=VideoStatus.QUEUED, created_at=base + timedelta(hours=1), filename="b.mp4")
    )
    target = await repo.insert(
        _make_doc(status=VideoStatus.QUEUED, created_at=base + timedelta(hours=2), filename="c.mp4")
    )
    await repo.insert(
        _make_doc(status=VideoStatus.QUEUED, created_at=base + timedelta(hours=3), filename="d.mp4")
    )

    count = await repo.count_queued_before(target.id)
    assert count == 2


async def test_count_queued_before_ignores_non_queued(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    base = datetime(2026, 1, 1, tzinfo=UTC)
    await repo.insert(_make_doc(status=VideoStatus.READY, created_at=base, filename="ready.mp4"))
    await repo.insert(
        _make_doc(status=VideoStatus.QUEUED, created_at=base + timedelta(hours=1), filename="q.mp4")
    )
    target = await repo.insert(
        _make_doc(status=VideoStatus.QUEUED, created_at=base + timedelta(hours=2), filename="t.mp4")
    )

    count = await repo.count_queued_before(target.id)
    assert count == 1
