import asyncio
import hashlib
import json
import subprocess
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path


class MediaProbeError(Exception):
    pass


class ThumbnailExtractionError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ProbeResult:
    duration_sec: float
    has_video_stream: bool


def _run_subprocess(args: list[str]) -> subprocess.CompletedProcess[bytes]:
    # subprocess.run via asyncio.to_thread avoids the WindowsSelectorEventLoop
    # NotImplementedError that asyncio.create_subprocess_exec raises under uvicorn.
    return subprocess.run(args, capture_output=True, check=False)


async def probe(path: Path) -> ProbeResult:
    if not path.exists():
        raise MediaProbeError(f"source file not found: {path}")

    result = await asyncio.to_thread(
        _run_subprocess,
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
    )
    if result.returncode != 0:
        raise MediaProbeError(result.stderr.decode("utf-8", errors="replace").strip())

    try:
        data = json.loads(result.stdout)
        duration = float(data["format"]["duration"])
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        raise MediaProbeError(f"could not parse ffprobe output: {exc}") from exc

    has_video = any(stream.get("codec_type") == "video" for stream in data.get("streams", []))
    return ProbeResult(duration_sec=duration, has_video_stream=has_video)


async def extract_thumbnail(source: Path, *, output_path: Path) -> None:
    if not source.exists():
        raise ThumbnailExtractionError(f"source file not found: {source}")

    probed = await probe(source)
    offset = max(probed.duration_sec * 0.1, 0.0)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result = await asyncio.to_thread(
        _run_subprocess,
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{offset:.3f}",
            "-i",
            str(source),
            "-vframes",
            "1",
            "-vf",
            "scale=320:-1",
            "-q:v",
            "5",
            str(output_path),
        ],
    )
    if result.returncode != 0:
        raise ThumbnailExtractionError(result.stderr.decode("utf-8", errors="replace").strip())


async def hash_stream(reader: AsyncIterator[bytes]) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    async for chunk in reader:
        digest.update(chunk)
        total += len(chunk)
    return digest.hexdigest(), total


def hash_file(path: Path, chunk_size: int = 64 * 1024) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            digest.update(chunk)
            total += len(chunk)
    return digest.hexdigest(), total
