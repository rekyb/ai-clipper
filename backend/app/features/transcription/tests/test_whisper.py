import asyncio
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.models.loader import WhisperHandle
from app.features.transcription.whisper import WhisperService


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


def _fake_info(duration: float = 5.0, language: str = "en") -> Any:
    return SimpleNamespace(language=language, language_probability=0.99, duration=duration)


def _fake_segments(n: int = 3) -> list[FakeSegment]:
    return [
        FakeSegment(
            start=float(i),
            end=float(i + 1),
            text=f"hello-{i}",
            avg_logprob=-0.1,
            no_speech_prob=0.01,
            words=[
                FakeWord(word=f"hello{i}", start=float(i), end=float(i) + 0.5, probability=0.95)
            ],
        )
        for i in range(n)
    ]


def _make_handle(segments: list[FakeSegment], info: Any) -> WhisperHandle:
    class _Model:
        def transcribe(self, _path: str, **_kwargs: Any) -> tuple[Any, Any]:
            return iter(segments), info

    return WhisperHandle(name="whisper-medium", path=Path("/x"), model=_Model())


async def test_transcribe_returns_collected_segments_and_info() -> None:
    handle = _make_handle(_fake_segments(3), _fake_info(duration=3.0))
    service = WhisperService(handle)
    collected = []

    async def on_segment(done: int, total: int, seg: Any) -> None:
        collected.append((done, total, seg.text))

    result = await service.transcribe(Path("/audio.mp4"), on_segment=on_segment)
    assert len(result.segments) == 3
    assert result.info.language == "en"
    assert result.info.language_probability == 0.99
    assert result.info.duration == pytest.approx(3.0)


async def test_transcribe_invokes_on_segment_for_every_segment() -> None:
    handle = _make_handle(_fake_segments(4), _fake_info(duration=4.0))
    service = WhisperService(handle)
    calls: list[tuple[int, int, str]] = []

    async def on_segment(done: int, total: int, seg: Any) -> None:
        calls.append((done, total, seg.text))

    await service.transcribe(Path("/audio.mp4"), on_segment=on_segment)
    assert [c[0] for c in calls] == [1, 2, 3, 4]
    assert all(c[1] >= 1 for c in calls)


async def test_transcribe_on_segment_callback_runs_in_event_loop() -> None:
    handle = _make_handle(_fake_segments(2), _fake_info(duration=2.0))
    service = WhisperService(handle)
    loop_seen: list[asyncio.AbstractEventLoop] = []

    async def on_segment(_done: int, _total: int, _seg: Any) -> None:
        loop_seen.append(asyncio.get_running_loop())

    main_loop = asyncio.get_running_loop()
    await service.transcribe(Path("/audio.mp4"), on_segment=on_segment)
    assert all(loop is main_loop for loop in loop_seen)


async def test_transcribe_estimates_total_from_duration() -> None:
    handle = _make_handle(_fake_segments(2), _fake_info(duration=10.0))
    service = WhisperService(handle)
    totals: list[int] = []

    async def on_segment(_done: int, total: int, _seg: Any) -> None:
        totals.append(total)

    await service.transcribe(Path("/audio.mp4"), on_segment=on_segment)
    # Estimate is max(1, int(duration / 5.0)) = 2 for duration=10
    assert totals[0] == 2
