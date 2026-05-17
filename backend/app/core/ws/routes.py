import contextlib
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.core.db.client import get_db
from app.core.schemas.video_status import VideoStatus
from app.core.ws.manager import ws_manager
from app.features.import_.repository import VideoRepository
from app.features.import_.schemas import VideoDocument
from app.features.transcription.schemas import ProgressEvent

log = structlog.get_logger("ws.routes")

router = APIRouter()

_TERMINAL_STATES = {VideoStatus.READY, VideoStatus.FAILED}


def get_video_repository() -> VideoRepository:
    return VideoRepository(get_db())


async def _build_snapshot(video: VideoDocument, repo: VideoRepository) -> ProgressEvent:
    queue_position: int | None = None
    if video.status is VideoStatus.QUEUED:
        before = await repo.count_queued_before(video.id)
        queue_position = before + 1
    return ProgressEvent(
        type="snapshot",
        video_id=video.id,
        status=video.status,
        percent=video.last_progress_percent or (100 if video.status is VideoStatus.READY else 0),
        stage="transcription",
        elapsed_sec=0.0,
        queue_position=queue_position,
        error_code=video.error_code,
        error_message=video.error_message,
    )


def _build_terminal_event(video: VideoDocument) -> ProgressEvent:
    if video.status is VideoStatus.READY:
        return ProgressEvent(
            type="complete",
            video_id=video.id,
            status=VideoStatus.READY,
            percent=100,
            stage="transcription",
            elapsed_sec=0.0,
        )
    return ProgressEvent(
        type="error",
        video_id=video.id,
        status=VideoStatus.FAILED,
        percent=video.last_progress_percent or 0,
        stage="transcription",
        elapsed_sec=0.0,
        error_code=video.error_code,
        error_message=video.error_message,
    )


def _error_event(video_id: str, code: str, message: str) -> ProgressEvent:
    return ProgressEvent(
        type="error",
        video_id=video_id,
        status=VideoStatus.FAILED,
        percent=0,
        stage="transcription",
        elapsed_sec=0.0,
        error_code=code,
        error_message=message,
    )


@router.websocket("/ws/{video_id}")
async def transcription_ws(
    ws: WebSocket,
    video_id: str,
    repo: Annotated[VideoRepository, Depends(get_video_repository)],
) -> None:
    await ws.accept()
    video = await repo.get_by_id(video_id)
    if video is None:
        await ws.send_json(
            _error_event(video_id, "JOB_NOT_FOUND", "video not found").model_dump(by_alias=True)
        )
        await ws.close()
        return

    snapshot = await _build_snapshot(video, repo)
    await ws.send_json(snapshot.model_dump(by_alias=True))

    if video.status in _TERMINAL_STATES:
        final = _build_terminal_event(video)
        await ws.send_json(final.model_dump(by_alias=True))
        await ws.close()
        return

    await ws_manager.subscribe(video_id, ws)
    try:
        while True:
            # Hold the connection; ignore inbound payloads.
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        log.warning("ws_loop_error", video_id=video_id, error=str(exc))
    finally:
        with contextlib.suppress(Exception):
            await ws_manager.disconnect(video_id, ws)
