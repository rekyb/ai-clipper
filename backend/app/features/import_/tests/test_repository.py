from datetime import UTC, datetime, timedelta

import pytest
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.features.import_.repository import VideoRepository
from app.features.import_.schemas import VideoDocument, VideoSource, VideoStatus


def _make_doc(
    *,
    filename: str = "sample.mp4",
    title: str = "Sample",
    status: VideoStatus = VideoStatus.IMPORTED,
    content_hash: str | None = "hash-default",
    created_at: datetime | None = None,
) -> VideoDocument:
    now = created_at or datetime.now(UTC)
    return VideoDocument(
        filename=filename,
        title=title,
        source=VideoSource.UPLOAD,
        source_url=None,
        storage_path=f"/media/originals/{filename}",
        thumbnail_path=None,
        duration_sec=120.0,
        file_size_bytes=1_000_000,
        container="mp4",
        content_hash=content_hash,
        status=status,
        error_code=None,
        error_message=None,
        created_at=now,
        updated_at=now,
    )


async def test_insert_assigns_objectid_string(test_db: AsyncIOMotorDatabase) -> None:
    repo = VideoRepository(test_db)
    inserted = await repo.insert(_make_doc())
    assert inserted.id != ""
    assert len(inserted.id) == 24


async def test_insert_honors_preset_id(test_db: AsyncIOMotorDatabase) -> None:
    from bson import ObjectId as Oid

    preset = str(Oid())
    doc = _make_doc()
    doc = doc.model_copy(update={"id": preset})
    inserted = await VideoRepository(test_db).insert(doc)
    assert inserted.id == preset


async def test_insert_persists_camelcase_keys_in_mongo(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    await repo.insert(_make_doc())
    raw = await test_db["videos"].find_one({})
    assert raw is not None
    assert "storagePath" in raw
    assert "contentHash" in raw
    assert "createdAt" in raw


async def test_get_by_id_returns_inserted_doc(test_db: AsyncIOMotorDatabase) -> None:
    repo = VideoRepository(test_db)
    inserted = await repo.insert(_make_doc(filename="alpha.mp4"))
    fetched = await repo.get_by_id(inserted.id)
    assert fetched is not None
    assert fetched.id == inserted.id
    assert fetched.filename == "alpha.mp4"


async def test_get_by_id_returns_none_for_missing(test_db: AsyncIOMotorDatabase) -> None:
    repo = VideoRepository(test_db)
    fetched = await repo.get_by_id("65f1a2b3c4d5e6f7a8b9c0d1")
    assert fetched is None


async def test_get_by_id_returns_none_for_malformed_id(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    fetched = await repo.get_by_id("not-an-objectid")
    assert fetched is None


async def test_find_by_hash_returns_matching_doc(test_db: AsyncIOMotorDatabase) -> None:
    repo = VideoRepository(test_db)
    inserted = await repo.insert(_make_doc(content_hash="abc123"))
    found = await repo.find_by_hash("abc123")
    assert found is not None
    assert found.id == inserted.id


async def test_find_by_hash_returns_none_when_no_match(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    await repo.insert(_make_doc(content_hash="abc123"))
    found = await repo.find_by_hash("def456")
    assert found is None


async def test_find_by_hash_ignores_null_hashes(test_db: AsyncIOMotorDatabase) -> None:
    repo = VideoRepository(test_db)
    await repo.insert(_make_doc(content_hash=None, status=VideoStatus.UPLOADING))
    found = await repo.find_by_hash("anything")
    assert found is None


async def test_list_videos_returns_all_when_no_status_filter(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    await repo.insert(_make_doc(filename="a.mp4"))
    await repo.insert(_make_doc(filename="b.mp4"))
    await repo.insert(_make_doc(filename="c.mp4"))
    videos = await repo.list_videos(status=None)
    assert len(videos) == 3


async def test_list_videos_filters_by_status(test_db: AsyncIOMotorDatabase) -> None:
    repo = VideoRepository(test_db)
    await repo.insert(_make_doc(filename="a.mp4", status=VideoStatus.IMPORTED))
    await repo.insert(_make_doc(filename="b.mp4", status=VideoStatus.IMPORTED))
    await repo.insert(_make_doc(filename="c.mp4", status=VideoStatus.UPLOADING))
    only_uploading = await repo.list_videos(status=VideoStatus.UPLOADING)
    assert len(only_uploading) == 1
    assert only_uploading[0].filename == "c.mp4"


async def test_list_videos_sorted_newest_first(test_db: AsyncIOMotorDatabase) -> None:
    repo = VideoRepository(test_db)
    base = datetime(2026, 1, 1, tzinfo=UTC)
    await repo.insert(_make_doc(filename="old.mp4", created_at=base))
    await repo.insert(_make_doc(filename="mid.mp4", created_at=base + timedelta(hours=1)))
    await repo.insert(_make_doc(filename="new.mp4", created_at=base + timedelta(hours=2)))
    videos = await repo.list_videos(status=None)
    assert [v.filename for v in videos] == ["new.mp4", "mid.mp4", "old.mp4"]


async def test_update_status_changes_status_and_bumps_updated_at(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    original_time = datetime(2026, 1, 1, tzinfo=UTC)
    inserted = await repo.insert(_make_doc(status=VideoStatus.UPLOADING, created_at=original_time))
    updated = await repo.update_status(inserted.id, status=VideoStatus.IMPORTED)
    assert updated is not None
    assert updated.status is VideoStatus.IMPORTED
    assert updated.updated_at > original_time


async def test_update_status_can_set_metadata_fields(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    inserted = await repo.insert(_make_doc(status=VideoStatus.UPLOADING))
    updated = await repo.update_status(
        inserted.id,
        status=VideoStatus.IMPORTED,
        duration_sec=180.5,
        thumbnail_path="/media/thumbnails/x.jpg",
        content_hash="freshhash",
    )
    assert updated is not None
    assert updated.duration_sec == 180.5
    assert updated.thumbnail_path == "/media/thumbnails/x.jpg"
    assert updated.content_hash == "freshhash"


async def test_update_status_returns_none_for_missing(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    result = await repo.update_status("65f1a2b3c4d5e6f7a8b9c0d1", status=VideoStatus.FAILED)
    assert result is None


async def test_delete_removes_doc(test_db: AsyncIOMotorDatabase) -> None:
    repo = VideoRepository(test_db)
    inserted = await repo.insert(_make_doc())
    deleted = await repo.delete(inserted.id)
    assert deleted is True
    assert await repo.get_by_id(inserted.id) is None


async def test_delete_returns_false_when_missing(test_db: AsyncIOMotorDatabase) -> None:
    repo = VideoRepository(test_db)
    deleted = await repo.delete("65f1a2b3c4d5e6f7a8b9c0d1")
    assert deleted is False


async def test_delete_returns_false_for_malformed_id(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    deleted = await repo.delete("not-an-objectid")
    assert deleted is False


@pytest.mark.parametrize(
    "status",
    [VideoStatus.UPLOADING, VideoStatus.IMPORTED, VideoStatus.FAILED],
)
async def test_round_trip_for_each_status(
    test_db: AsyncIOMotorDatabase, status: VideoStatus
) -> None:
    repo = VideoRepository(test_db)
    inserted = await repo.insert(_make_doc(status=status))
    fetched = await repo.get_by_id(inserted.id)
    assert fetched is not None
    assert fetched.status is status
