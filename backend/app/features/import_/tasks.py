import asyncio
import shutil
from pathlib import Path

import structlog

from app.core.config import Settings
from app.features.import_.errors import (
    DuplicateVideoError,
    DurationExceededError,
    UnsupportedFormatError,
)
from app.features.import_.media import (
    MediaProbeError,
    ThumbnailExtractionError,
    extract_thumbnail,
    hash_file,
    probe,
)
from app.features.import_.repository import VideoRepository
from app.features.import_.schemas import VideoStatus
from app.features.import_.service import _cleanup_paths, _sanitize_filename
from app.features.import_.youtube import YoutubeDownloadError, download_to

log = structlog.get_logger("import.tasks")


async def _mark_failed(repo: VideoRepository, video_id: str, code: str, message: str) -> None:
    await repo.update_status(
        video_id,
        status=VideoStatus.FAILED,
        error_code=code,
        error_message=message,
    )


async def run_youtube_import(
    video_id: str,
    url: str,
    *,
    repo: VideoRepository,
    settings: Settings,
) -> None:
    temp_dir = settings.originals_dir / ".tmp" / video_id
    final_dir = settings.originals_dir / video_id
    thumbnail_path = settings.thumbnails_dir / f"{video_id}.jpg"
    final_path: Path | None = None

    try:
        result = await asyncio.to_thread(download_to, url, temp_dir)
        downloaded = result.filename
        container = downloaded.suffix.lstrip(".").lower()
        if container not in settings.supported_containers:
            raise UnsupportedFormatError(f"unsupported container: .{container}")

        try:
            probed = await probe(downloaded)
        except MediaProbeError as exc:
            raise UnsupportedFormatError(f"could not probe file: {exc}") from exc
        if not probed.has_video_stream:
            raise UnsupportedFormatError("no video stream found")
        if probed.duration_sec > settings.max_duration_seconds:
            raise DurationExceededError(
                f"duration {probed.duration_sec:.1f}s exceeds {settings.max_duration_seconds}s"
            )

        content_hash, total_bytes = await asyncio.to_thread(hash_file, downloaded)
        existing = await repo.find_by_hash(content_hash)
        if existing is not None:
            raise DuplicateVideoError(
                f"video already imported as '{existing.title}'",
                existing_title=existing.title,
            )

        sanitized = _sanitize_filename(result.title + downloaded.suffix)
        final_dir.mkdir(parents=True, exist_ok=True)
        final_path = final_dir / sanitized
        shutil.move(str(downloaded), str(final_path))

        try:
            await extract_thumbnail(final_path, output_path=thumbnail_path)
        except ThumbnailExtractionError as exc:
            raise UnsupportedFormatError(f"thumbnail extraction failed: {exc}") from exc

        await repo.update_status(
            video_id,
            status=VideoStatus.IMPORTED,
            title=result.title,
            storage_path=str(final_path),
            thumbnail_path=str(thumbnail_path),
            duration_sec=probed.duration_sec,
            content_hash=content_hash,
            file_size_bytes=total_bytes,
            container=container,
        )
        _cleanup_temp_dir(temp_dir)

    except YoutubeDownloadError as exc:
        log.warning("youtube_download_failed", video_id=video_id, code=exc.code)
        await _mark_failed(repo, video_id, exc.code, str(exc))
        _cleanup_paths(temp_dir, final_path, thumbnail_path, final_dir)
    except Exception as exc:
        code = getattr(exc, "code", "DOWNLOAD_FAILED")
        log.warning("youtube_import_failed", video_id=video_id, code=code, error=str(exc))
        await _mark_failed(repo, video_id, code, str(exc))
        _cleanup_paths(temp_dir, final_path, thumbnail_path, final_dir)


def _cleanup_temp_dir(temp_dir: Path) -> None:
    if not temp_dir.exists():
        return
    try:
        shutil.rmtree(temp_dir)
    except OSError as exc:
        log.warning("cleanup_failed", path=str(temp_dir), error=str(exc))
