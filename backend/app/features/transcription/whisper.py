import asyncio
from collections.abc import Callable, Coroutine
from concurrent.futures import Future
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.models.loader import WhisperHandle

OnSegmentCallback = Callable[[int, int, Any], Coroutine[Any, Any, None]]


@dataclass(frozen=True)
class TranscriptionResult:
    segments: list[Any]
    info: Any


class WhisperService:
    def __init__(self, handle: WhisperHandle) -> None:
        self._handle = handle

    async def transcribe(
        self,
        audio_path: Path,
        *,
        on_segment: OnSegmentCallback,
    ) -> TranscriptionResult:
        loop = asyncio.get_running_loop()

        def _dispatch(done: int, total: int, seg: Any) -> None:
            coro = on_segment(done, total, seg)
            future: Future[None] = asyncio.run_coroutine_threadsafe(coro, loop)
            future.result()

        def _do_transcribe() -> TranscriptionResult:
            segments_iter, info = self._handle.model.transcribe(
                str(audio_path),
                word_timestamps=True,
                vad_filter=True,
                beam_size=1,
            )
            duration = getattr(info, "duration", 0.0) or 0.0
            total_estimate = max(1, int(duration / 5.0))
            collected: list[Any] = []
            for idx, seg in enumerate(segments_iter):
                collected.append(seg)
                _dispatch(idx + 1, total_estimate, seg)
            return TranscriptionResult(segments=collected, info=info)

        return await asyncio.to_thread(_do_transcribe)
