from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import Settings, get_settings
from app.features.import_.repository import VideoRepository
from app.features.import_.routes import get_video_repository
from app.main import app


def _override_settings(tmp_path: Path, **overrides: object) -> Settings:
    media_dir = tmp_path / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    kwargs: dict[str, object] = {
        "media_dir": media_dir,
        "max_file_size_bytes": 100 * 1024 * 1024,
        "max_duration_seconds": 60,
    }
    kwargs.update(overrides)
    return Settings(_env_file=None, **kwargs)  # type: ignore[arg-type]


@pytest_asyncio.fixture
async def client(
    test_db: AsyncIOMotorDatabase,
    tmp_path: Path,
) -> AsyncIterator[AsyncClient]:
    settings = _override_settings(tmp_path)
    repo = VideoRepository(test_db)
    app.dependency_overrides[get_video_repository] = lambda: repo
    app.dependency_overrides[get_settings] = lambda: settings
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def short_cap_client(
    test_db: AsyncIOMotorDatabase,
    tmp_path: Path,
) -> AsyncIterator[AsyncClient]:
    settings = _override_settings(tmp_path, max_duration_seconds=2)
    repo = VideoRepository(test_db)
    app.dependency_overrides[get_video_repository] = lambda: repo
    app.dependency_overrides[get_settings] = lambda: settings
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def tiny_cap_client(
    test_db: AsyncIOMotorDatabase,
    tmp_path: Path,
) -> AsyncIterator[AsyncClient]:
    settings = _override_settings(tmp_path, max_file_size_bytes=1024)
    repo = VideoRepository(test_db)
    app.dependency_overrides[get_video_repository] = lambda: repo
    app.dependency_overrides[get_settings] = lambda: settings
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def test_upload_returns_201_with_imported_record(
    client: AsyncClient,
    fixture_videos: dict[str, Path],
) -> None:
    with fixture_videos["mp4"].open("rb") as f:
        response = await client.post(
            "/api/videos/upload", files={"file": ("sample.mp4", f, "video/mp4")}
        )
    assert response.status_code == 201
    body = response.json()
    assert body["error"] is None
    data = body["data"]
    assert data["status"] == "imported"
    assert data["filename"] == "sample.mp4"
    assert data["container"] == "mp4"
    assert 4.5 <= data["duration_sec"] <= 5.5


async def test_upload_rejects_unsupported_container_with_422(
    client: AsyncClient,
    fixture_videos: dict[str, Path],
) -> None:
    with fixture_videos["mp4"].open("rb") as f:
        response = await client.post(
            "/api/videos/upload", files={"file": ("sample.txt", f, "text/plain")}
        )
    assert response.status_code == 422
    body = response.json()
    assert body["data"] is None
    assert body["error"]["code"] == "UNSUPPORTED_FORMAT"


async def test_upload_rejects_audio_only_with_422(
    client: AsyncClient,
    fixture_videos: dict[str, Path],
) -> None:
    with fixture_videos["audio_only"].open("rb") as f:
        response = await client.post(
            "/api/videos/upload",
            files={"file": ("audio_only.mp4", f, "video/mp4")},
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNSUPPORTED_FORMAT"


async def test_upload_rejects_oversize_with_413(
    tiny_cap_client: AsyncClient,
    fixture_videos: dict[str, Path],
) -> None:
    with fixture_videos["mp4"].open("rb") as f:
        response = await tiny_cap_client.post(
            "/api/videos/upload", files={"file": ("sample.mp4", f, "video/mp4")}
        )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


async def test_upload_rejects_long_duration_with_422(
    short_cap_client: AsyncClient,
    fixture_videos: dict[str, Path],
) -> None:
    with fixture_videos["mp4"].open("rb") as f:
        response = await short_cap_client.post(
            "/api/videos/upload", files={"file": ("sample.mp4", f, "video/mp4")}
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "DURATION_EXCEEDED"


async def test_upload_rejects_duplicate_with_409(
    client: AsyncClient,
    fixture_videos: dict[str, Path],
) -> None:
    with fixture_videos["mp4"].open("rb") as f:
        first = await client.post(
            "/api/videos/upload", files={"file": ("sample.mp4", f, "video/mp4")}
        )
    assert first.status_code == 201

    with fixture_videos["mp4"].open("rb") as f:
        second = await client.post(
            "/api/videos/upload", files={"file": ("sample.mp4", f, "video/mp4")}
        )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "DUPLICATE_VIDEO"


async def test_upload_with_missing_filename_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/api/videos/upload",
        files={"file": ("", b"some bytes", "application/octet-stream")},
    )
    assert response.status_code in (400, 422)


async def test_download_url_returns_202_with_placeholder(client: AsyncClient) -> None:
    with patch("app.features.import_.routes.run_youtube_import", new=AsyncMock()):
        response = await client.post(
            "/api/videos/download-url",
            json={"url": "https://youtu.be/dQw4w9WgXcQ"},
        )
    assert response.status_code == 202
    body = response.json()
    assert body["error"] is None
    data = body["data"]
    assert data["status"] == "uploading"
    assert data["source"] == "youtube"
    assert data["source_url"] == "https://youtu.be/dQw4w9WgXcQ"


async def test_download_url_schedules_background_task(client: AsyncClient) -> None:
    spy = AsyncMock()
    with patch("app.features.import_.routes.run_youtube_import", new=spy):
        response = await client.post(
            "/api/videos/download-url",
            json={"url": "https://www.youtube.com/watch?v=abc"},
        )
    assert response.status_code == 202
    spy.assert_awaited_once()
    assert spy.await_args is not None
    args, kwargs = spy.await_args
    assert args[1] == "https://www.youtube.com/watch?v=abc"
    assert len(args[0]) == 24  # ObjectId hex
    assert "repo" in kwargs
    assert "settings" in kwargs


async def test_download_url_rejects_vimeo_host_with_400(client: AsyncClient) -> None:
    with patch("app.features.import_.routes.run_youtube_import", new=AsyncMock()):
        response = await client.post(
            "/api/videos/download-url",
            json={"url": "https://vimeo.com/12345"},
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNSUPPORTED_HOST"


async def test_download_url_rejects_garbage_url_with_422(client: AsyncClient) -> None:
    response = await client.post("/api/videos/download-url", json={"url": "not-a-url"})
    assert response.status_code == 422


async def test_list_returns_empty_array_when_no_videos(client: AsyncClient) -> None:
    response = await client.get("/api/videos")
    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["data"]["videos"] == []


async def test_list_returns_uploaded_video(
    client: AsyncClient, fixture_videos: dict[str, Path]
) -> None:
    with fixture_videos["mp4"].open("rb") as f:
        await client.post("/api/videos/upload", files={"file": ("sample.mp4", f, "video/mp4")})
    listed = await client.get("/api/videos")
    assert listed.status_code == 200
    videos = listed.json()["data"]["videos"]
    assert len(videos) == 1
    assert videos[0]["filename"] == "sample.mp4"
    assert videos[0]["status"] == "imported"


async def test_list_filters_by_status(client: AsyncClient) -> None:
    with patch("app.features.import_.routes.run_youtube_import", new=AsyncMock()):
        await client.post("/api/videos/download-url", json={"url": "https://youtu.be/x"})
    filtered = await client.get("/api/videos?status=uploading")
    body = filtered.json()
    assert filtered.status_code == 200
    assert len(body["data"]["videos"]) == 1
    assert body["data"]["videos"][0]["status"] == "uploading"


async def test_delete_removes_record_and_files(
    client: AsyncClient, fixture_videos: dict[str, Path]
) -> None:
    with fixture_videos["mp4"].open("rb") as f:
        upload = await client.post(
            "/api/videos/upload", files={"file": ("sample.mp4", f, "video/mp4")}
        )
    video_id = upload.json()["data"]["id"]
    storage_path = Path(upload.json()["data"]["storage_path"])
    thumb_path = Path(upload.json()["data"]["thumbnail_path"])

    delete_response = await client.delete(f"/api/videos/{video_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["data"]["deleted"] is True
    assert not storage_path.exists()
    assert not thumb_path.exists()

    listed = await client.get("/api/videos")
    assert listed.json()["data"]["videos"] == []


async def test_delete_returns_404_for_missing(client: AsyncClient) -> None:
    response = await client.delete("/api/videos/65f1a2b3c4d5e6f7a8b9c0d1")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_delete_returns_404_for_malformed_id(client: AsyncClient) -> None:
    response = await client.delete("/api/videos/not-an-objectid")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_thumbnail_static_mount_serves_uploaded_thumbnail(
    client: AsyncClient, fixture_videos: dict[str, Path]
) -> None:
    with fixture_videos["mp4"].open("rb") as f:
        upload = await client.post(
            "/api/videos/upload", files={"file": ("sample.mp4", f, "video/mp4")}
        )
    thumb_path = Path(upload.json()["data"]["thumbnail_path"])
    response = await client.get(f"/media/thumbnails/{thumb_path.name}")
    assert response.status_code == 200
    assert response.content[:3] == b"\xff\xd8\xff"
