from collections.abc import AsyncIterator
from pathlib import Path

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
