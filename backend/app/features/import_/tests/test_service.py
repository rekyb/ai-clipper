from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from app.core.config import Settings
from app.features.import_.errors import (
    DuplicateVideoError,
    DurationExceededError,
    UnsupportedFormatError,
    VideoTooLargeError,
)
from app.features.import_.repository import VideoRepository
from app.features.import_.schemas import VideoDocument, VideoSource, VideoStatus
from app.features.import_.service import _sanitize_filename, import_uploaded_file


class FakeVideoRepository:
    def __init__(self) -> None:
        self.inserted: list[VideoDocument] = []
        self.hash_lookup: VideoDocument | None = None

    async def insert(self, doc: VideoDocument) -> VideoDocument:
        self.inserted.append(doc)
        return doc

    async def find_by_hash(self, content_hash: str) -> VideoDocument | None:
        return self.hash_lookup


def _fake_repo() -> VideoRepository:
    return cast(VideoRepository, FakeVideoRepository())


def _make_settings(tmp_path: Path, **overrides: Any) -> Settings:
    media_dir = tmp_path / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    kwargs: dict[str, Any] = {
        "media_dir": media_dir,
        "max_file_size_bytes": 100 * 1024 * 1024,
        "max_duration_seconds": 60,
    }
    kwargs.update(overrides)
    return Settings(_env_file=None, **kwargs)


def _existing_video(content_hash: str, title: str) -> VideoDocument:
    now = datetime.now(UTC)
    return VideoDocument(
        filename="prior.mp4",
        title=title,
        source=VideoSource.UPLOAD,
        source_url=None,
        storage_path="/x",
        thumbnail_path=None,
        duration_sec=10.0,
        file_size_bytes=1,
        container="mp4",
        content_hash=content_hash,
        status=VideoStatus.IMPORTED,
        error_code=None,
        error_message=None,
        created_at=now,
        updated_at=now,
    )


async def _file_chunks(path: Path, chunk_size: int = 64 * 1024) -> AsyncIterator[bytes]:
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            yield chunk


def test_sanitize_strips_path_components() -> None:
    assert _sanitize_filename("../../etc/passwd") == "passwd"
    assert _sanitize_filename("C:\\Windows\\evil.mp4") == "evil.mp4"


def test_sanitize_replaces_unsafe_chars() -> None:
    result = _sanitize_filename("weird:name?.mp4")
    assert result == "weird_name_.mp4"


def test_sanitize_preserves_extension_on_truncation() -> None:
    long_stem = "a" * 250
    result = _sanitize_filename(f"{long_stem}.mp4")
    assert result.endswith(".mp4")
    assert len(result) <= 200


def test_sanitize_handles_empty_input() -> None:
    assert _sanitize_filename("") == "video"
    assert _sanitize_filename("///") == "video"


async def test_import_returns_imported_record(
    tmp_path: Path,
    fixture_videos: dict[str, Path],
) -> None:
    settings = _make_settings(tmp_path)
    repo = FakeVideoRepository()
    result = await import_uploaded_file(
        filename="sample.mp4",
        chunks=_file_chunks(fixture_videos["mp4"]),
        repo=cast(VideoRepository, repo),
        settings=settings,
    )
    assert result.status is VideoStatus.IMPORTED
    assert result.filename == "sample.mp4"
    assert result.container == "mp4"
    assert result.duration_sec is not None
    assert 4.5 <= result.duration_sec <= 5.5
    assert result.content_hash is not None
    assert len(result.content_hash) == 64
    assert result.file_size_bytes > 0
    assert len(repo.inserted) == 1


async def test_import_writes_final_file_under_originals_dir(
    tmp_path: Path,
    fixture_videos: dict[str, Path],
) -> None:
    settings = _make_settings(tmp_path)
    result = await import_uploaded_file(
        filename="sample.mp4",
        chunks=_file_chunks(fixture_videos["mp4"]),
        repo=_fake_repo(),
        settings=settings,
    )
    final_path = Path(result.storage_path)
    assert final_path.exists()
    assert final_path.is_file()
    assert settings.originals_dir in final_path.parents


async def test_import_creates_thumbnail_jpeg(
    tmp_path: Path,
    fixture_videos: dict[str, Path],
) -> None:
    settings = _make_settings(tmp_path)
    result = await import_uploaded_file(
        filename="sample.mp4",
        chunks=_file_chunks(fixture_videos["mp4"]),
        repo=_fake_repo(),
        settings=settings,
    )
    assert result.thumbnail_path is not None
    thumb = Path(result.thumbnail_path)
    assert thumb.exists()
    assert thumb.read_bytes()[:3] == b"\xff\xd8\xff"


async def test_import_cleans_up_temp_directory(
    tmp_path: Path,
    fixture_videos: dict[str, Path],
) -> None:
    settings = _make_settings(tmp_path)
    await import_uploaded_file(
        filename="sample.mp4",
        chunks=_file_chunks(fixture_videos["mp4"]),
        repo=_fake_repo(),
        settings=settings,
    )
    tmp_dir = settings.originals_dir / ".tmp"
    if tmp_dir.exists():
        assert list(tmp_dir.iterdir()) == []


async def test_import_rejects_unsupported_container(
    tmp_path: Path,
    fixture_videos: dict[str, Path],
) -> None:
    settings = _make_settings(tmp_path)
    with pytest.raises(UnsupportedFormatError, match="container"):
        await import_uploaded_file(
            filename="sample.txt",
            chunks=_file_chunks(fixture_videos["mp4"]),
            repo=_fake_repo(),
            settings=settings,
        )


async def test_import_rejects_audio_only_file(
    tmp_path: Path,
    fixture_videos: dict[str, Path],
) -> None:
    settings = _make_settings(tmp_path)
    with pytest.raises(UnsupportedFormatError, match="video stream"):
        await import_uploaded_file(
            filename="audio_only.mp4",
            chunks=_file_chunks(fixture_videos["audio_only"]),
            repo=_fake_repo(),
            settings=settings,
        )


async def test_import_rejects_oversize_file(
    tmp_path: Path,
    fixture_videos: dict[str, Path],
) -> None:
    settings = _make_settings(tmp_path, max_file_size_bytes=1024)
    with pytest.raises(VideoTooLargeError):
        await import_uploaded_file(
            filename="sample.mp4",
            chunks=_file_chunks(fixture_videos["mp4"]),
            repo=_fake_repo(),
            settings=settings,
        )


async def test_import_rejects_duration_exceeding_cap(
    tmp_path: Path,
    fixture_videos: dict[str, Path],
) -> None:
    settings = _make_settings(tmp_path, max_duration_seconds=2)
    with pytest.raises(DurationExceededError):
        await import_uploaded_file(
            filename="sample.mp4",
            chunks=_file_chunks(fixture_videos["mp4"]),
            repo=_fake_repo(),
            settings=settings,
        )


async def test_import_rejects_duplicate_hash(
    tmp_path: Path,
    fixture_videos: dict[str, Path],
) -> None:
    settings = _make_settings(tmp_path)
    repo = FakeVideoRepository()
    repo.hash_lookup = _existing_video("existing", "Prior Video")
    with pytest.raises(DuplicateVideoError) as exc_info:
        await import_uploaded_file(
            filename="sample.mp4",
            chunks=_file_chunks(fixture_videos["mp4"]),
            repo=cast(VideoRepository, repo),
            settings=settings,
        )
    assert exc_info.value.existing_title == "Prior Video"


async def test_import_cleans_up_on_duplicate_rejection(
    tmp_path: Path,
    fixture_videos: dict[str, Path],
) -> None:
    settings = _make_settings(tmp_path)
    repo = FakeVideoRepository()
    repo.hash_lookup = _existing_video("x", "Prior")
    with pytest.raises(DuplicateVideoError):
        await import_uploaded_file(
            filename="sample.mp4",
            chunks=_file_chunks(fixture_videos["mp4"]),
            repo=cast(VideoRepository, repo),
            settings=settings,
        )
    tmp_dir = settings.originals_dir / ".tmp"
    if tmp_dir.exists():
        assert list(tmp_dir.iterdir()) == []
