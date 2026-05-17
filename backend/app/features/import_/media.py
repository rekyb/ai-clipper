import asyncio
import hashlib
import json
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


async def probe(path: Path) -> ProbeResult:
    if not path.exists():
        raise MediaProbeError(f"source file not found: {path}")

    proc = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise MediaProbeError(stderr.decode("utf-8", errors="replace").strip())

    try:
        data = json.loads(stdout)
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
    proc = await asyncio.create_subprocess_exec(
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
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise ThumbnailExtractionError(stderr.decode("utf-8", errors="replace").strip())


async def hash_stream(reader: AsyncIterator[bytes]) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    async for chunk in reader:
        digest.update(chunk)
        total += len(chunk)
    return digest.hexdigest(), total
