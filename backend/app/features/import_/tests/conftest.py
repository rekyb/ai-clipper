import asyncio
import os
import subprocess
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

TEST_DB_NAME = "ai_clipper_import_test"


@pytest_asyncio.fixture
async def test_db() -> AsyncIterator[AsyncIOMotorDatabase]:
    uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(uri, tz_aware=True, serverSelectionTimeoutMS=2000)
    db = client[TEST_DB_NAME]
    await client.drop_database(TEST_DB_NAME)
    try:
        yield db
    finally:
        await client.drop_database(TEST_DB_NAME)
        client.close()


def _run_ffmpeg(args: list[str]) -> None:
    result = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")


@pytest.fixture(scope="session")
def fixture_videos(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    tmp = tmp_path_factory.mktemp("import_fixtures")
    mp4 = tmp / "sample.mp4"
    mkv = tmp / "sample.mkv"
    audio_only = tmp / "audio_only.mp4"

    common_video = [
        "-f",
        "lavfi",
        "-i",
        "color=c=blue:size=320x240:rate=24",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-t",
        "5",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
    ]
    _run_ffmpeg([*common_video, str(mp4)])
    _run_ffmpeg([*common_video, str(mkv)])

    audio_args = [
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-t",
        "3",
        "-c:a",
        "aac",
        str(audio_only),
    ]
    _run_ffmpeg(audio_args)

    return {"mp4": mp4, "mkv": mkv, "audio_only": audio_only}


@pytest.fixture
def thumbs_dir(tmp_path: Path) -> Path:
    d = tmp_path / "thumbnails"
    d.mkdir()
    return d


async def _aiter_bytes(chunks: list[bytes]) -> AsyncIterator[bytes]:
    for chunk in chunks:
        await asyncio.sleep(0)
        yield chunk


@pytest.fixture
def make_byte_stream() -> Callable[[list[bytes]], AsyncIterator[bytes]]:
    def _factory(chunks: list[bytes]) -> AsyncIterator[bytes]:
        return _aiter_bytes(chunks)

    return _factory
