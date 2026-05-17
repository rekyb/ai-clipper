from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.schemas.video_status import VideoStatus
from app.core.ws import manager as ws_manager_module
from app.core.ws.routes import get_video_repository, router
from app.features.import_.schemas import VideoDocument, VideoSource


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


def _make_video(
    *,
    video_id: str = "65f1a2b3c4d5e6f7a8b9c0d1",
    status: VideoStatus = VideoStatus.QUEUED,
    last_progress_percent: int | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> VideoDocument:
    now = datetime.now(UTC)
    return VideoDocument(
        id=video_id,
        filename="x.mp4",
        title="x",
        source=VideoSource.UPLOAD,
        source_url=None,
        storage_path="/x",
        thumbnail_path=None,
        duration_sec=10.0,
        file_size_bytes=1,
        container="mp4",
        content_hash="hash-x",
        status=status,
        error_code=error_code,
        error_message=error_message,
        created_at=now,
        updated_at=now,
        last_progress_percent=last_progress_percent,
    )


def _override_repo(app: FastAPI, **methods: Any) -> AsyncMock:
    repo = AsyncMock()
    for name, value in methods.items():
        setattr(repo, name, value)
    app.dependency_overrides[get_video_repository] = lambda: repo
    return repo


@pytest.fixture(autouse=True)
def _reset_manager() -> None:
    ws_manager_module.ws_manager._topics.clear()


def test_ws_sends_snapshot_for_queued_video() -> None:
    app = _make_app()
    video = _make_video(status=VideoStatus.QUEUED)
    _override_repo(
        app,
        get_by_id=AsyncMock(return_value=video),
        count_queued_before=AsyncMock(return_value=2),
    )
    with TestClient(app).websocket_connect(f"/ws/{video.id}") as ws:
        snap = ws.receive_json()
    assert snap["type"] == "snapshot"
    assert snap["videoId"] == video.id
    assert snap["status"] == "queued"
    assert snap["percent"] == 0
    assert snap["queuePosition"] == 3  # 0-indexed before-count -> 1-indexed display position


def test_ws_sends_snapshot_for_transcribing_video_with_progress() -> None:
    app = _make_app()
    video = _make_video(status=VideoStatus.TRANSCRIBING, last_progress_percent=42)
    _override_repo(app, get_by_id=AsyncMock(return_value=video))
    with TestClient(app).websocket_connect(f"/ws/{video.id}") as ws:
        snap = ws.receive_json()
    assert snap["type"] == "snapshot"
    assert snap["status"] == "transcribing"
    assert snap["percent"] == 42
    assert snap["queuePosition"] is None


def test_ws_sends_complete_and_closes_for_ready_video() -> None:
    app = _make_app()
    video = _make_video(status=VideoStatus.READY, last_progress_percent=100)
    _override_repo(app, get_by_id=AsyncMock(return_value=video))
    with TestClient(app).websocket_connect(f"/ws/{video.id}") as ws:
        snap = ws.receive_json()
        final = ws.receive_json()
    assert snap["type"] == "snapshot"
    assert snap["status"] == "ready"
    assert snap["percent"] == 100
    assert final["type"] == "complete"


def test_ws_sends_error_and_closes_for_failed_video() -> None:
    app = _make_app()
    video = _make_video(
        status=VideoStatus.FAILED,
        error_code="AUDIO_DECODE_FAILED",
        error_message="bad audio",
    )
    _override_repo(app, get_by_id=AsyncMock(return_value=video))
    with TestClient(app).websocket_connect(f"/ws/{video.id}") as ws:
        snap = ws.receive_json()
        final = ws.receive_json()
    assert snap["type"] == "snapshot"
    assert snap["status"] == "failed"
    assert final["type"] == "error"
    assert final["errorCode"] == "AUDIO_DECODE_FAILED"
    assert final["errorMessage"] == "bad audio"


def test_ws_rejects_unknown_video_with_error_event() -> None:
    app = _make_app()
    _override_repo(app, get_by_id=AsyncMock(return_value=None))
    with TestClient(app).websocket_connect("/ws/nope") as ws:
        msg = ws.receive_json()
    assert msg["type"] == "error"
    assert msg["errorCode"] == "JOB_NOT_FOUND"


def test_ws_subscribes_then_disconnect_cleans_up() -> None:
    app = _make_app()
    video = _make_video(status=VideoStatus.QUEUED)
    _override_repo(
        app,
        get_by_id=AsyncMock(return_value=video),
        count_queued_before=AsyncMock(return_value=0),
    )
    mgr = ws_manager_module.ws_manager
    with TestClient(app).websocket_connect(f"/ws/{video.id}") as ws:
        ws.receive_json()  # snapshot
        # Connection held; manager should now have 1 subscriber on the topic.
        # The handler's subscribe runs after the snapshot send.
        assert mgr.subscriber_count(video.id) == 1
    # After ws context closes, disconnect handler should run.
    # Give the disconnect a moment by checking eventually.
    # In TestClient, by the time we exit the context, the lifecycle has finished.
    assert mgr.subscriber_count(video.id) == 0
