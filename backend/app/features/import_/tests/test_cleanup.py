import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.features.import_.cleanup import (
    mark_stale_uploading_as_failed,
    sweep_stale_temp_files,
)
from app.features.import_.repository import VideoRepository
from app.features.import_.schemas import VideoDocument, VideoSource, VideoStatus


def _set_mtime(path: Path, age_hours: float) -> None:
    past = time.time() - age_hours * 3600
    os.utime(path, (past, past))


def test_sweep_removes_old_temp_files(tmp_path: Path) -> None:
    tmp_dir = tmp_path / ".tmp"
    tmp_dir.mkdir(parents=True)
    stale = tmp_dir / "stale"
    stale.write_bytes(b"x")
    fresh = tmp_dir / "fresh"
    fresh.write_bytes(b"y")
    _set_mtime(stale, age_hours=3)
    removed = sweep_stale_temp_files(tmp_path, max_age_hours=1.0)
    assert removed == 1
    assert not stale.exists()
    assert fresh.exists()


def test_sweep_handles_missing_tmp_dir(tmp_path: Path) -> None:
    removed = sweep_stale_temp_files(tmp_path / "no_such_originals")
    assert removed == 0


def test_sweep_removes_stale_subdirectories(tmp_path: Path) -> None:
    tmp_dir = tmp_path / ".tmp"
    tmp_dir.mkdir(parents=True)
    stale_dir = tmp_dir / "abc"
    stale_dir.mkdir()
    (stale_dir / "leftover.mp4").write_bytes(b"x")
    _set_mtime(stale_dir, age_hours=2)
    sweep_stale_temp_files(tmp_path, max_age_hours=1.0)
    assert not stale_dir.exists()


async def test_mark_stale_uploading_flips_to_failed(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    old = datetime.now(UTC) - timedelta(hours=2)
    fresh = datetime.now(UTC)
    await repo.insert(_uploading_doc(updated_at=old, filename="stale.mp4"))
    await repo.insert(_uploading_doc(updated_at=fresh, filename="fresh.mp4"))

    marked = await mark_stale_uploading_as_failed(repo, max_age_hours=1.0)
    assert marked == 1
    failed = await repo.list_videos(status=VideoStatus.FAILED)
    assert len(failed) == 1
    assert failed[0].filename == "stale.mp4"
    assert failed[0].error_code == "INTERRUPTED"


async def test_mark_stale_noop_when_all_recent(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    await repo.insert(_uploading_doc(updated_at=datetime.now(UTC)))
    marked = await mark_stale_uploading_as_failed(repo, max_age_hours=1.0)
    assert marked == 0


def _uploading_doc(*, updated_at: datetime, filename: str = "x.mp4") -> VideoDocument:
    return VideoDocument(
        filename=filename,
        title=filename,
        source=VideoSource.UPLOAD,
        source_url=None,
        storage_path="",
        thumbnail_path=None,
        duration_sec=None,
        file_size_bytes=0,
        container=None,
        content_hash=None,
        status=VideoStatus.UPLOADING,
        error_code=None,
        error_message=None,
        created_at=updated_at,
        updated_at=updated_at,
    )
