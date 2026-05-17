from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import pytest_asyncio
from bson import ObjectId
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.schemas.video_status import VideoStatus
from app.features.import_.repository import VideoRepository
from app.features.import_.schemas import VideoDocument, VideoSource
from app.features.transcription.repository import TranscriptRepository
from app.features.transcription.routes import (
    get_transcript_repository,
    get_video_repository,
    register_exception_handlers,
    router,
)
from app.features.transcription.schemas import Segment, TranscriptDocument, Word


def _make_app(repo: VideoRepository, transcript_repo: TranscriptRepository) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    register_exception_handlers(app)
    app.dependency_overrides[get_video_repository] = lambda: repo
    app.dependency_overrides[get_transcript_repository] = lambda: transcript_repo
    return app


def _make_video(
    *, status: VideoStatus, error_code: str | None = None, error_message: str | None = None
) -> VideoDocument:
    now = datetime.now(UTC)
    return VideoDocument(
        id=str(ObjectId()),
        filename="x.mp4",
        title="x",
        source=VideoSource.UPLOAD,
        source_url=None,
        storage_path="/x",
        thumbnail_path=None,
        duration_sec=10.0,
        file_size_bytes=1,
        container="mp4",
        content_hash=f"hash-{status.value}",
        status=status,
        error_code=error_code,
        error_message=error_message,
        created_at=now,
        updated_at=now,
    )


def _make_transcript(video_id: str) -> TranscriptDocument:
    return TranscriptDocument(
        id=str(ObjectId()),
        video_id=video_id,
        language="en",
        language_probability=0.99,
        duration_sec=5.0,
        model_name="medium",
        model_version="float16",
        segments=[
            Segment(
                start=0.0,
                end=5.0,
                text="hello",
                avg_logprob=-0.1,
                no_speech_prob=0.01,
                words=[Word(word="hello", start=0.0, end=0.5, probability=0.97)],
            )
        ],
        created_at=datetime(2026, 5, 17, 10, 30, tzinfo=UTC),
    )


@pytest_asyncio.fixture
async def client(
    test_db: AsyncIOMotorDatabase,
) -> AsyncIterator[AsyncClient]:
    app = _make_app(VideoRepository(test_db), TranscriptRepository(test_db))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as ac:
        yield ac


async def test_retry_returns_200_and_flips_failed_to_queued(
    client: AsyncClient, test_db: AsyncIOMotorDatabase
) -> None:
    repo = VideoRepository(test_db)
    inserted = await repo.insert(
        _make_video(status=VideoStatus.FAILED, error_code="X", error_message="x")
    )
    resp = await client.post(f"/api/videos/{inserted.id}/retry")
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    assert body["data"]["status"] == "queued"


async def test_retry_returns_200_with_current_status_when_already_queued(
    client: AsyncClient, test_db: AsyncIOMotorDatabase
) -> None:
    repo = VideoRepository(test_db)
    inserted = await repo.insert(_make_video(status=VideoStatus.QUEUED))
    resp = await client.post(f"/api/videos/{inserted.id}/retry")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "queued"


async def test_retry_returns_409_when_video_uploading(
    client: AsyncClient, test_db: AsyncIOMotorDatabase
) -> None:
    repo = VideoRepository(test_db)
    inserted = await repo.insert(_make_video(status=VideoStatus.UPLOADING))
    resp = await client.post(f"/api/videos/{inserted.id}/retry")
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"]["code"] == "INVALID_TRANSITION"


async def test_retry_returns_404_when_video_missing(client: AsyncClient) -> None:
    resp = await client.post(f"/api/videos/{ObjectId()}/retry")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


async def test_retry_reruns_youtube_import_when_storage_path_empty(
    client: AsyncClient, test_db: AsyncIOMotorDatabase
) -> None:
    repo = VideoRepository(test_db)
    doc = _make_video(status=VideoStatus.FAILED, error_code="VIDEO_AUTH_REQUIRED")
    doc = doc.model_copy(
        update={
            "source": VideoSource.YOUTUBE,
            "source_url": "https://youtu.be/x",
            "storage_path": "",
        }
    )
    inserted = await repo.insert(doc)

    captured: dict[str, Any] = {}

    async def fake_run_youtube_import(
        video_id: str, url: str, *, repo: VideoRepository, settings: Any
    ) -> None:
        captured["video_id"] = video_id
        captured["url"] = url

    with patch(
        "app.features.transcription.routes.run_youtube_import", fake_run_youtube_import
    ):
        resp = await client.post(f"/api/videos/{inserted.id}/retry")

    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    assert body["data"]["status"] == "uploading"
    assert captured == {"video_id": inserted.id, "url": "https://youtu.be/x"}


async def test_retry_uses_transcription_path_when_storage_path_set(
    client: AsyncClient, test_db: AsyncIOMotorDatabase
) -> None:
    # A YouTube import that succeeded (file on disk) but transcription failed
    # should re-queue for transcription, NOT re-trigger the YouTube download.
    repo = VideoRepository(test_db)
    doc = _make_video(status=VideoStatus.FAILED, error_code="AUDIO_DECODE_FAILED")
    doc = doc.model_copy(
        update={
            "source": VideoSource.YOUTUBE,
            "source_url": "https://youtu.be/x",
            "storage_path": "/media/originals/abc/video.mp4",
        }
    )
    inserted = await repo.insert(doc)

    called = False

    async def fake_run_youtube_import(*args: Any, **kwargs: Any) -> None:
        nonlocal called
        called = True

    with patch(
        "app.features.transcription.routes.run_youtube_import", fake_run_youtube_import
    ):
        resp = await client.post(f"/api/videos/{inserted.id}/retry")

    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "queued"
    assert called is False, "must NOT re-trigger youtube import when file already exists"


async def test_transcript_get_returns_404_when_missing(
    client: AsyncClient,
) -> None:
    resp = await client.get(f"/api/videos/{ObjectId()}/transcript")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


async def test_transcript_get_returns_document(
    client: AsyncClient, test_db: AsyncIOMotorDatabase
) -> None:
    video_id = str(ObjectId())
    transcript_repo = TranscriptRepository(test_db)
    await transcript_repo.insert(_make_transcript(video_id))

    resp = await client.get(f"/api/videos/{video_id}/transcript")
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    assert body["data"]["videoId"] == video_id
    assert body["data"]["language"] == "en"
    assert body["data"]["segments"][0]["words"][0]["word"] == "hello"
