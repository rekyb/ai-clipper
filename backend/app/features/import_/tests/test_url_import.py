import asyncio
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.core.schemas.video_status import VideoStatus
from app.features.import_.errors import InvalidUrlError, UnsupportedHostError
from app.features.import_.repository import VideoRepository
from app.features.import_.schemas import VideoDocument, VideoSource
from app.features.import_.service import import_from_url
from app.features.import_.tasks import run_youtube_import
from app.features.import_.youtube import YoutubeResult


class FakeRepo:
    def __init__(self) -> None:
        self.docs: dict[str, VideoDocument] = {}
        self.hash_lookup: VideoDocument | None = None

    async def insert(self, doc: VideoDocument) -> VideoDocument:
        await asyncio.sleep(0)
        self.docs[doc.id] = doc
        return doc

    async def find_by_hash(self, content_hash: str) -> VideoDocument | None:
        await asyncio.sleep(0)
        return self.hash_lookup

    async def update_status(self, video_id: str, **fields: Any) -> VideoDocument | None:
        await asyncio.sleep(0)
        existing = self.docs.get(video_id)
        if existing is None:
            return None
        update_data = {k: v for k, v in fields.items() if v is not None}
        updated = existing.model_copy(update=update_data)
        self.docs[video_id] = updated
        return updated

    async def transition_status(
        self,
        video_id: str,
        *,
        from_status: object,
        to_status: VideoStatus,
        **_: object,
    ) -> VideoDocument | None:
        await asyncio.sleep(0)
        existing = self.docs.get(video_id)
        if existing is None:
            return None
        updated = existing.model_copy(update={"status": to_status})
        self.docs[video_id] = updated
        return updated


def _fake_repo() -> VideoRepository:
    return cast(VideoRepository, FakeRepo())


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


async def test_import_from_url_creates_uploading_placeholder(tmp_path: Path) -> None:
    repo = FakeRepo()
    settings = _make_settings(tmp_path)
    doc = await import_from_url(
        url="https://youtu.be/abc123", repo=cast(VideoRepository, repo), settings=settings
    )
    assert doc.status is VideoStatus.UPLOADING
    assert doc.source is VideoSource.YOUTUBE
    assert doc.source_url == "https://youtu.be/abc123"
    assert doc.id in repo.docs


@pytest.mark.parametrize(
    "url",
    [
        "https://youtube.com/watch?v=abc",
        "https://www.youtube.com/watch?v=abc",
        "https://m.youtube.com/watch?v=abc",
        "https://youtu.be/abc",
    ],
)
async def test_import_from_url_accepts_all_youtube_hosts(tmp_path: Path, url: str) -> None:
    doc = await import_from_url(url=url, repo=_fake_repo(), settings=_make_settings(tmp_path))
    assert doc.source_url == url


async def test_import_from_url_rejects_vimeo_host(tmp_path: Path) -> None:
    with pytest.raises(UnsupportedHostError, match=r"vimeo\.com"):
        await import_from_url(
            url="https://vimeo.com/12345",
            repo=_fake_repo(),
            settings=_make_settings(tmp_path),
        )


async def test_import_from_url_rejects_unparseable_url(tmp_path: Path) -> None:
    with pytest.raises(InvalidUrlError):
        await import_from_url(
            url="not-a-url",
            repo=_fake_repo(),
            settings=_make_settings(tmp_path),
        )


def _stage_downloaded_fixture(fixture: Path, target_dir: Path, title: str) -> YoutubeResult:
    target_dir.mkdir(parents=True, exist_ok=True)
    downloaded = target_dir / f"{title}.mp4"
    downloaded.write_bytes(fixture.read_bytes())
    return YoutubeResult(filename=downloaded, title=title, source_url="https://youtu.be/x")


async def test_run_youtube_import_marks_record_imported(
    tmp_path: Path, fixture_videos: dict[str, Path]
) -> None:
    repo = FakeRepo()
    settings = _make_settings(tmp_path)
    placeholder = await import_from_url(
        url="https://youtu.be/x",
        repo=cast(VideoRepository, repo),
        settings=settings,
    )

    def fake_download(_url: str, target_dir: Path, **_: Any) -> YoutubeResult:
        return _stage_downloaded_fixture(fixture_videos["mp4"], target_dir, "MyTitle")

    with patch("app.features.import_.tasks.download_to", fake_download):
        await run_youtube_import(
            placeholder.id,
            "https://youtu.be/x",
            repo=cast(VideoRepository, repo),
            settings=settings,
        )

    final = repo.docs[placeholder.id]
    # Chunk 2B auto-flips imported → queued after a successful YouTube import.
    assert final.status is VideoStatus.QUEUED
    assert final.title == "MyTitle"
    assert final.duration_sec is not None
    assert final.content_hash is not None
    assert final.thumbnail_path is not None
    assert Path(final.storage_path).exists()


async def test_run_youtube_import_marks_failed_on_download_error(
    tmp_path: Path,
) -> None:
    from app.features.import_.youtube import YoutubeDownloadError

    repo = FakeRepo()
    settings = _make_settings(tmp_path)
    placeholder = await import_from_url(
        url="https://youtu.be/x",
        repo=cast(VideoRepository, repo),
        settings=settings,
    )

    def fake_download(_url: str, _target_dir: Path, **_: Any) -> YoutubeResult:
        raise YoutubeDownloadError("private", code="VIDEO_PRIVATE")

    with patch("app.features.import_.tasks.download_to", fake_download):
        await run_youtube_import(
            placeholder.id,
            "https://youtu.be/x",
            repo=cast(VideoRepository, repo),
            settings=settings,
        )

    failed = repo.docs[placeholder.id]
    assert failed.status is VideoStatus.FAILED
    assert failed.error_code == "VIDEO_PRIVATE"


async def test_run_youtube_import_marks_failed_on_long_duration(
    tmp_path: Path, fixture_videos: dict[str, Path]
) -> None:
    repo = FakeRepo()
    settings = _make_settings(tmp_path, max_duration_seconds=2)
    placeholder = await import_from_url(
        url="https://youtu.be/x",
        repo=cast(VideoRepository, repo),
        settings=settings,
    )

    def fake_download(_url: str, target_dir: Path, **_: Any) -> YoutubeResult:
        return _stage_downloaded_fixture(fixture_videos["mp4"], target_dir, "Long")

    with patch("app.features.import_.tasks.download_to", fake_download):
        await run_youtube_import(
            placeholder.id,
            "https://youtu.be/x",
            repo=cast(VideoRepository, repo),
            settings=settings,
        )

    failed = repo.docs[placeholder.id]
    assert failed.status is VideoStatus.FAILED
    assert failed.error_code == "DURATION_EXCEEDED"


async def test_run_youtube_import_marks_failed_on_duplicate(
    tmp_path: Path, fixture_videos: dict[str, Path]
) -> None:
    repo = FakeRepo()
    settings = _make_settings(tmp_path)
    placeholder = await import_from_url(
        url="https://youtu.be/x",
        repo=cast(VideoRepository, repo),
        settings=settings,
    )
    repo.hash_lookup = placeholder.model_copy(
        update={"title": "Earlier Import", "id": "65f1a2b3c4d5e6f7a8b9c0d1"}
    )

    def fake_download(_url: str, target_dir: Path, **_: Any) -> YoutubeResult:
        return _stage_downloaded_fixture(fixture_videos["mp4"], target_dir, "Dup")

    with patch("app.features.import_.tasks.download_to", fake_download):
        await run_youtube_import(
            placeholder.id,
            "https://youtu.be/x",
            repo=cast(VideoRepository, repo),
            settings=settings,
        )

    failed = repo.docs[placeholder.id]
    assert failed.status is VideoStatus.FAILED
    assert failed.error_code == "DUPLICATE_VIDEO"


async def test_run_youtube_import_cleans_temp_on_failure(
    tmp_path: Path,
) -> None:
    from app.features.import_.youtube import YoutubeDownloadError

    repo = FakeRepo()
    settings = _make_settings(tmp_path)
    placeholder = await import_from_url(
        url="https://youtu.be/x",
        repo=cast(VideoRepository, repo),
        settings=settings,
    )

    def fake_download(_url: str, _target_dir: Path, **_: Any) -> YoutubeResult:
        raise YoutubeDownloadError("blocked", code="VIDEO_REGION_BLOCKED")

    with patch("app.features.import_.tasks.download_to", fake_download):
        await run_youtube_import(
            placeholder.id,
            "https://youtu.be/x",
            repo=cast(VideoRepository, repo),
            settings=settings,
        )

    tmp_dir = settings.originals_dir / ".tmp"
    if tmp_dir.exists():
        assert list(tmp_dir.iterdir()) == []
