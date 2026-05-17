import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import Settings
from app.core.gpu.vram import VRAMUnavailableError
from app.core.schemas.video_status import VideoStatus
from app.core.ws import manager as ws_manager_module
from app.core.ws.manager import ConnectionManager
from app.features.import_.repository import VideoRepository
from app.features.import_.schemas import VideoDocument, VideoSource
from app.features.transcription.errors import AudioDecodeFailedError
from app.features.transcription.repository import TranscriptRepository
from app.features.transcription.whisper import TranscriptionResult, WhisperService
from app.workers.transcription import TranscriptionWorker


@dataclass
class FakeWord:
    word: str
    start: float
    end: float
    probability: float


@dataclass
class FakeSegment:
    start: float
    end: float
    text: str
    avg_logprob: float
    no_speech_prob: float
    words: list[FakeWord]


def _fake_info(duration: float = 5.0) -> Any:
    return SimpleNamespace(language="en", language_probability=0.99, duration=duration)


def _fake_segments(n: int) -> list[FakeSegment]:
    return [
        FakeSegment(
            start=float(i),
            end=float(i + 1),
            text=f"seg-{i}",
            avg_logprob=-0.1,
            no_speech_prob=0.01,
            words=[FakeWord(word=f"w{i}", start=float(i), end=float(i) + 0.5, probability=0.95)],
        )
        for i in range(n)
    ]


def _make_video(
    *, status: VideoStatus = VideoStatus.QUEUED, filename: str = "x.mp4", duration: float = 10.0
) -> VideoDocument:
    now = datetime.now(UTC)
    return VideoDocument(
        id=str(ObjectId()),
        filename=filename,
        title=filename,
        source=VideoSource.UPLOAD,
        source_url=None,
        storage_path=f"/x/{filename}",
        thumbnail_path=None,
        duration_sec=duration,
        file_size_bytes=1,
        container="mp4",
        content_hash=f"hash-{filename}",
        status=status,
        error_code=None,
        error_message=None,
        created_at=now,
        updated_at=now,
    )


class FakeWhisperService(WhisperService):
    def __init__(
        self,
        *,
        segments: list[FakeSegment] | None = None,
        info: Any | None = None,
        raise_exc: Exception | None = None,
        per_segment_delay: float = 0.0,
    ) -> None:
        self._segments = segments if segments is not None else _fake_segments(2)
        self._info = info if info is not None else _fake_info(2.0)
        self._raise = raise_exc
        self._delay = per_segment_delay

    async def transcribe(self, audio_path: Path, *, on_segment: Any) -> TranscriptionResult:
        if self._raise is not None:
            raise self._raise
        for idx, seg in enumerate(self._segments):
            if self._delay:
                await asyncio.sleep(self._delay)
            await on_segment(idx + 1, len(self._segments), seg)
        return TranscriptionResult(segments=list(self._segments), info=self._info)


def _make_worker(
    *,
    test_db: AsyncIOMotorDatabase,
    whisper: WhisperService,
    settings: Settings | None = None,
    ws_manager: ConnectionManager | None = None,
) -> TranscriptionWorker:
    return TranscriptionWorker(
        repo=VideoRepository(test_db),
        transcript_repo=TranscriptRepository(test_db),
        ws_manager=ws_manager or ConnectionManager(),
        settings=settings or Settings(_env_file=None, skip_vram_guard=True),
        whisper_factory=lambda: whisper,
    )


@pytest.fixture(autouse=True)
def _reset_singleton_manager() -> None:
    ws_manager_module.ws_manager._topics.clear()


async def test_process_one_writes_transcript_and_flips_to_ready(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    inserted = await repo.insert(_make_video(status=VideoStatus.TRANSCRIBING))
    worker = _make_worker(test_db=test_db, whisper=FakeWhisperService())
    await worker.process_one(inserted)

    fetched = await repo.get_by_id(inserted.id)
    assert fetched is not None
    assert fetched.status is VideoStatus.READY
    assert fetched.transcription_finished_at is not None

    transcript = await TranscriptRepository(test_db).get_by_video_id(inserted.id)
    assert transcript is not None
    assert len(transcript.segments) == 2
    assert transcript.language == "en"
    assert transcript.model_name == "medium"


async def test_process_one_broadcasts_progress_and_complete(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    inserted = await repo.insert(_make_video(status=VideoStatus.TRANSCRIBING))
    received: list[Any] = []

    class _RecordingWs:
        async def send_json(self, payload: Any) -> None:
            received.append(payload)

    mgr = ConnectionManager()
    await mgr.subscribe(inserted.id, _RecordingWs())

    worker = _make_worker(
        test_db=test_db,
        whisper=FakeWhisperService(segments=_fake_segments(2)),
        ws_manager=mgr,
        settings=Settings(
            _env_file=None,
            skip_vram_guard=True,
            transcription_progress_throttle_sec=0.0,  # disable throttling for this test
        ),
    )
    await worker.process_one(inserted)

    types = [m["type"] for m in received]
    assert types.count("progress") >= 1
    assert types[-1] == "complete"
    assert received[-1]["status"] == "ready"


async def test_process_one_handles_vram_unavailable(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    inserted = await repo.insert(_make_video(status=VideoStatus.TRANSCRIBING))

    def _failing_factory() -> WhisperService:
        raise VRAMUnavailableError(requested_bytes=2_500_000_000, available_bytes=500_000_000)

    worker = TranscriptionWorker(
        repo=VideoRepository(test_db),
        transcript_repo=TranscriptRepository(test_db),
        ws_manager=ConnectionManager(),
        settings=Settings(_env_file=None, skip_vram_guard=True),
        whisper_factory=_failing_factory,
    )
    await worker.process_one(inserted)

    fetched = await repo.get_by_id(inserted.id)
    assert fetched is not None
    assert fetched.status is VideoStatus.FAILED
    assert fetched.error_code == "VRAM_UNAVAILABLE"


async def test_process_one_handles_audio_decode_failure(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    inserted = await repo.insert(_make_video(status=VideoStatus.TRANSCRIBING))
    worker = _make_worker(
        test_db=test_db,
        whisper=FakeWhisperService(raise_exc=AudioDecodeFailedError("bad audio")),
    )
    await worker.process_one(inserted)

    fetched = await repo.get_by_id(inserted.id)
    assert fetched is not None
    assert fetched.status is VideoStatus.FAILED
    assert fetched.error_code == "AUDIO_DECODE_FAILED"


async def test_process_one_handles_generic_exception_as_transcription_failed(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    inserted = await repo.insert(_make_video(status=VideoStatus.TRANSCRIBING))
    worker = _make_worker(
        test_db=test_db,
        whisper=FakeWhisperService(raise_exc=RuntimeError("kaboom")),
    )
    await worker.process_one(inserted)

    fetched = await repo.get_by_id(inserted.id)
    assert fetched is not None
    assert fetched.status is VideoStatus.FAILED
    assert fetched.error_code == "TRANSCRIPTION_FAILED"


async def test_process_one_handles_timeout(test_db: AsyncIOMotorDatabase) -> None:
    repo = VideoRepository(test_db)
    inserted = await repo.insert(_make_video(status=VideoStatus.TRANSCRIBING, duration=0.5))
    worker = _make_worker(
        test_db=test_db,
        whisper=FakeWhisperService(per_segment_delay=2.0),
        settings=Settings(
            _env_file=None,
            skip_vram_guard=True,
            transcription_timeout_multiplier=0.1,  # 0.5 * 0.1 = 50ms — guarantees timeout
        ),
    )
    await worker.process_one(inserted)

    fetched = await repo.get_by_id(inserted.id)
    assert fetched is not None
    assert fetched.status is VideoStatus.FAILED
    assert fetched.error_code == "TRANSCRIPTION_TIMEOUT"


async def test_process_one_updates_last_progress_percent(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    inserted = await repo.insert(_make_video(status=VideoStatus.TRANSCRIBING))
    worker = _make_worker(
        test_db=test_db,
        whisper=FakeWhisperService(segments=_fake_segments(4)),
        settings=Settings(
            _env_file=None,
            skip_vram_guard=True,
            transcription_progress_throttle_sec=0.0,
        ),
    )
    await worker.process_one(inserted)
    # After completion the worker should write 100; intermediate updates also went out.
    fetched = await repo.get_by_id(inserted.id)
    assert fetched is not None
    assert fetched.last_progress_percent is not None


async def test_run_forever_processes_queue_then_idles(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    await repo.insert(_make_video(status=VideoStatus.QUEUED, filename="a.mp4"))
    await repo.insert(_make_video(status=VideoStatus.QUEUED, filename="b.mp4"))

    worker = _make_worker(
        test_db=test_db,
        whisper=FakeWhisperService(),
        settings=Settings(
            _env_file=None,
            skip_vram_guard=True,
            transcription_poll_interval_sec=0.05,
            transcription_progress_throttle_sec=0.0,
        ),
    )
    task = asyncio.create_task(worker.run_forever())
    # Allow the worker time to drain the queue.
    for _ in range(50):
        await asyncio.sleep(0.05)
        ready_count = len(await repo.list_videos(status=VideoStatus.READY))
        if ready_count == 2:
            break
    worker.cancel()
    task.cancel()
    with __import__("contextlib").suppress(asyncio.CancelledError):
        await task

    ready = await repo.list_videos(status=VideoStatus.READY)
    assert len(ready) == 2
