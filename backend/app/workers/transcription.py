import asyncio
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from bson import ObjectId

from app.core.config import Settings
from app.core.gpu.vram import VRAMUnavailableError
from app.core.schemas.video_status import VideoStatus
from app.core.ws.manager import ConnectionManager
from app.features.import_.repository import VideoRepository
from app.features.import_.schemas import VideoDocument
from app.features.transcription.errors import (
    AudioDecodeFailedError,
    WorkerErrorCode,
)
from app.features.transcription.repository import TranscriptRepository
from app.features.transcription.schemas import (
    ProgressEvent,
    Segment,
    TranscriptDocument,
    Word,
)
from app.features.transcription.whisper import WhisperService

log = structlog.get_logger("workers.transcription")

WhisperFactory = Callable[[], WhisperService]


def _default_whisper_factory() -> WhisperService:
    from app.core.models.loader import load_whisper_medium

    return WhisperService(load_whisper_medium())


def _segment_to_pydantic(seg: Any) -> Segment:
    words = [
        Word(
            word=str(w.word),
            start=float(w.start),
            end=float(w.end),
            probability=float(w.probability),
        )
        for w in (seg.words or [])
    ]
    return Segment(
        start=float(seg.start),
        end=float(seg.end),
        text=str(seg.text),
        avg_logprob=float(getattr(seg, "avg_logprob", 0.0)),
        no_speech_prob=float(getattr(seg, "no_speech_prob", 0.0)),
        words=words,
    )


class TranscriptionWorker:
    def __init__(
        self,
        *,
        repo: VideoRepository,
        transcript_repo: TranscriptRepository,
        ws_manager: ConnectionManager,
        settings: Settings,
        whisper_factory: WhisperFactory | None = None,
    ) -> None:
        self._repo = repo
        self._transcript_repo = transcript_repo
        self._ws_manager = ws_manager
        self._settings = settings
        self._whisper_factory = whisper_factory or _default_whisper_factory
        self._whisper: WhisperService | None = None
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    async def run_forever(self) -> None:
        while not self._cancelled:
            video = await self._repo.claim_next_queued()
            if video is None:
                await asyncio.sleep(self._settings.transcription_poll_interval_sec)
                continue
            try:
                await self.process_one(video)
            except Exception as exc:
                log.exception("transcription_unexpected", video_id=video.id, error=str(exc))
                await self._fail(
                    video.id,
                    WorkerErrorCode.TRANSCRIPTION_FAILED.value,
                    str(exc),
                    elapsed_sec=0.0,
                )

    async def process_one(self, video: VideoDocument) -> None:
        started = time.monotonic()
        last_emit = 0.0
        throttle = self._settings.transcription_progress_throttle_sec
        timeout_sec = max(
            1.0, self._settings.transcription_timeout_multiplier * (video.duration_sec or 1.0)
        )

        try:
            whisper = self._ensure_whisper()
        except VRAMUnavailableError as exc:
            await self._fail(
                video.id, WorkerErrorCode.VRAM_UNAVAILABLE.value, str(exc), elapsed_sec=0.0
            )
            return
        except Exception as exc:
            await self._fail(
                video.id,
                WorkerErrorCode.TRANSCRIPTION_FAILED.value,
                f"model load failed: {exc}",
                elapsed_sec=0.0,
            )
            return

        async def on_segment(done: int, total: int, seg: Any) -> None:
            nonlocal last_emit
            percent = min(99, max(1, int(done / max(total, 1) * 100)))
            elapsed = time.monotonic() - started
            await self._repo.update_progress(video.id, percent=percent)
            now = time.monotonic()
            if throttle <= 0 or (now - last_emit) >= throttle:
                last_emit = now
                eta = (elapsed / done) * (total - done) if done > 0 else None
                event = ProgressEvent(
                    type="progress",
                    video_id=video.id,
                    status=VideoStatus.TRANSCRIBING,
                    percent=percent,
                    stage="transcription",
                    segments_done=done,
                    segments_total=total,
                    elapsed_sec=elapsed,
                    eta_sec=eta,
                )
                await self._ws_manager.broadcast(video.id, event.model_dump(by_alias=True))

        try:
            result = await asyncio.wait_for(
                whisper.transcribe(Path(video.storage_path), on_segment=on_segment),
                timeout=timeout_sec,
            )
        except TimeoutError:
            elapsed = time.monotonic() - started
            await self._fail(
                video.id,
                WorkerErrorCode.TRANSCRIPTION_TIMEOUT.value,
                f"transcription exceeded {timeout_sec:.0f}s",
                elapsed_sec=elapsed,
            )
            return
        except AudioDecodeFailedError as exc:
            elapsed = time.monotonic() - started
            await self._fail(
                video.id,
                WorkerErrorCode.AUDIO_DECODE_FAILED.value,
                str(exc),
                elapsed_sec=elapsed,
            )
            return
        except Exception as exc:
            elapsed = time.monotonic() - started
            await self._fail(
                video.id,
                WorkerErrorCode.TRANSCRIPTION_FAILED.value,
                str(exc),
                elapsed_sec=elapsed,
            )
            return

        info = result.info
        transcript = TranscriptDocument(
            id=str(ObjectId()),
            video_id=video.id,
            language=getattr(info, "language", "unknown"),
            language_probability=float(getattr(info, "language_probability", 0.0)),
            duration_sec=float(getattr(info, "duration", 0.0) or 0.0),
            model_name="medium",
            model_version=self._settings.whisper_compute_type,
            segments=[_segment_to_pydantic(s) for s in result.segments],
            created_at=datetime.now(UTC),
        )
        await self._transcript_repo.insert(transcript)
        await self._repo.transition_status(
            video.id,
            from_status=VideoStatus.TRANSCRIBING,
            to_status=VideoStatus.READY,
            set_fields={
                "transcriptionFinishedAt": datetime.now(UTC),
                "lastProgressPercent": 100,
            },
        )
        elapsed = time.monotonic() - started
        complete = ProgressEvent(
            type="complete",
            video_id=video.id,
            status=VideoStatus.READY,
            percent=100,
            stage="transcription",
            segments_done=len(result.segments),
            segments_total=len(result.segments),
            elapsed_sec=elapsed,
        )
        await self._ws_manager.broadcast(video.id, complete.model_dump(by_alias=True))
        log.info(
            "transcription_completed",
            video_id=video.id,
            segments=len(result.segments),
            duration_sec=transcript.duration_sec,
            wall_time_sec=elapsed,
        )

    def _ensure_whisper(self) -> WhisperService:
        if self._whisper is None:
            self._whisper = self._whisper_factory()
        return self._whisper

    async def _fail(
        self,
        video_id: str,
        code: str,
        message: str,
        *,
        elapsed_sec: float,
    ) -> None:
        await self._repo.transition_status(
            video_id,
            from_status={VideoStatus.TRANSCRIBING, VideoStatus.QUEUED},
            to_status=VideoStatus.FAILED,
            set_fields={"transcriptionFinishedAt": datetime.now(UTC)},
            error_code=code,
            error_message=message,
        )
        event = ProgressEvent(
            type="error",
            video_id=video_id,
            status=VideoStatus.FAILED,
            percent=0,
            stage="transcription",
            elapsed_sec=elapsed_sec,
            error_code=code,
            error_message=message,
        )
        await self._ws_manager.broadcast(video_id, event.model_dump(by_alias=True))
        log.warning("transcription_failed", video_id=video_id, code=code, message=message)
