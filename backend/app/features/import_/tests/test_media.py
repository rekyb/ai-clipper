import hashlib
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest

from app.features.import_.media import (
    MediaProbeError,
    ThumbnailExtractionError,
    extract_thumbnail,
    hash_stream,
    probe,
)


async def test_probe_returns_duration_for_mp4(fixture_videos: dict[str, Path]) -> None:
    result = await probe(fixture_videos["mp4"])
    assert 4.5 <= result.duration_sec <= 5.5
    assert result.has_video_stream is True


async def test_probe_returns_duration_for_mkv(fixture_videos: dict[str, Path]) -> None:
    result = await probe(fixture_videos["mkv"])
    assert 4.5 <= result.duration_sec <= 5.5
    assert result.has_video_stream is True


async def test_probe_flags_audio_only_file_as_having_no_video_stream(
    fixture_videos: dict[str, Path],
) -> None:
    result = await probe(fixture_videos["audio_only"])
    assert result.has_video_stream is False
    assert 2.5 <= result.duration_sec <= 3.5


async def test_probe_raises_for_missing_file(tmp_path: Path) -> None:
    with pytest.raises(MediaProbeError):
        await probe(tmp_path / "does_not_exist.mp4")


async def test_probe_raises_for_non_media_file(tmp_path: Path) -> None:
    junk = tmp_path / "junk.mp4"
    junk.write_bytes(b"not a real video file")
    with pytest.raises(MediaProbeError):
        await probe(junk)


async def test_extract_thumbnail_creates_jpeg(
    fixture_videos: dict[str, Path],
    thumbs_dir: Path,
) -> None:
    output = thumbs_dir / "test.jpg"
    await extract_thumbnail(fixture_videos["mp4"], output_path=output)
    assert output.exists()
    assert output.stat().st_size > 0
    assert output.read_bytes()[:3] == b"\xff\xd8\xff"  # JPEG SOI marker


async def test_extract_thumbnail_overwrites_existing(
    fixture_videos: dict[str, Path],
    thumbs_dir: Path,
) -> None:
    output = thumbs_dir / "test.jpg"
    output.write_bytes(b"stale")
    await extract_thumbnail(fixture_videos["mp4"], output_path=output)
    assert output.read_bytes()[:3] == b"\xff\xd8\xff"


async def test_extract_thumbnail_raises_for_missing_source(
    tmp_path: Path,
    thumbs_dir: Path,
) -> None:
    with pytest.raises(ThumbnailExtractionError):
        await extract_thumbnail(tmp_path / "nope.mp4", output_path=thumbs_dir / "x.jpg")


async def test_hash_stream_returns_known_sha256(
    make_byte_stream: Callable[[list[bytes]], AsyncIterator[bytes]],
) -> None:
    chunks = [b"hello ", b"world"]
    expected = hashlib.sha256(b"hello world").hexdigest()
    digest, total = await hash_stream(make_byte_stream(chunks))
    assert digest == expected
    assert total == 11


async def test_hash_stream_handles_empty_input(
    make_byte_stream: Callable[[list[bytes]], AsyncIterator[bytes]],
) -> None:
    expected = hashlib.sha256(b"").hexdigest()
    digest, total = await hash_stream(make_byte_stream([]))
    assert digest == expected
    assert total == 0


async def test_hash_stream_counts_large_input(
    make_byte_stream: Callable[[list[bytes]], AsyncIterator[bytes]],
) -> None:
    chunks = [b"x" * 1024 for _ in range(10)]
    digest, total = await hash_stream(make_byte_stream(chunks))
    assert total == 10 * 1024
    assert digest == hashlib.sha256(b"x" * 10240).hexdigest()
