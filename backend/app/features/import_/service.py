import hashlib
import re
import shutil
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path, PurePath
from urllib.parse import urlparse

import structlog
from bson import ObjectId

from app.core.config import Settings
from app.features.import_.errors import (
    DuplicateVideoError,
    DurationExceededError,
    InvalidUrlError,
    StorageError,
    UnsupportedFormatError,
    UnsupportedHostError,
    VideoNotFoundError,
    VideoTooLargeError,
)
from app.features.import_.media import (
    MediaProbeError,
    ThumbnailExtractionError,
    extract_thumbnail,
    probe,
)
from app.features.import_.repository import VideoRepository
from app.features.import_.schemas import VideoDocument, VideoSource, VideoStatus

log = structlog.get_logger("import.service")

_UNSAFE_CHARS = re.compile(r'[/\\:*?"<>|\x00-\x1f]')


def _sanitize_filename(filename: str) -> str:
    name = PurePath(filename).name
    name = _UNSAFE_CHARS.sub("_", name).strip()
    if not name:
        return "video"
    if len(name) <= 200:
        return name
    stem, dot, ext = name.rpartition(".")
    if dot and len(ext) <= 10:
        return stem[: 200 - len(dot) - len(ext)] + dot + ext
    return name[:200]


def _cleanup_paths(*paths: Path | None) -> None:
    for p in paths:
        if p is None or not p.exists():
            continue
        try:
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
        except OSError as exc:
            log.warning("cleanup_failed", path=str(p), error=str(exc))


async def _stream_to_disk(
    chunks: AsyncIterator[bytes],
    target: Path,
    max_bytes: int,
) -> tuple[str, int]:
    target.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    total = 0
    with target.open("wb") as out:
        async for chunk in chunks:
            if total + len(chunk) > max_bytes:
                raise VideoTooLargeError(f"file exceeds {max_bytes} bytes")
            out.write(chunk)
            digest.update(chunk)
            total += len(chunk)
    return digest.hexdigest(), total


async def import_uploaded_file(
    *,
    filename: str,
    chunks: AsyncIterator[bytes],
    repo: VideoRepository,
    settings: Settings,
) -> VideoDocument:
    video_id = str(ObjectId())
    container = PurePath(filename).suffix.lstrip(".").lower()
    if container not in settings.supported_containers:
        raise UnsupportedFormatError(f"unsupported container: .{container}")

    temp_path = settings.originals_dir / ".tmp" / video_id
    final_dir = settings.originals_dir / video_id
    thumbnail_path = settings.thumbnails_dir / f"{video_id}.jpg"

    final_path: Path | None = None

    try:
        content_hash, total_bytes = await _stream_to_disk(
            chunks, temp_path, settings.max_file_size_bytes
        )

        try:
            probed = await probe(temp_path)
        except MediaProbeError as exc:
            raise UnsupportedFormatError(f"could not probe file: {exc}") from exc

        if not probed.has_video_stream:
            raise UnsupportedFormatError("no video stream found")
        if probed.duration_sec > settings.max_duration_seconds:
            raise DurationExceededError(
                f"duration {probed.duration_sec:.1f}s exceeds {settings.max_duration_seconds}s"
            )

        existing = await repo.find_by_hash(content_hash)
        if existing is not None:
            raise DuplicateVideoError(
                f"video already imported as '{existing.title}'",
                existing_title=existing.title,
            )

        sanitized = _sanitize_filename(filename)
        final_dir.mkdir(parents=True, exist_ok=True)
        final_path = final_dir / sanitized
        shutil.move(str(temp_path), str(final_path))

        try:
            await extract_thumbnail(final_path, output_path=thumbnail_path)
        except ThumbnailExtractionError as exc:
            raise StorageError(f"thumbnail extraction failed: {exc}") from exc

        now = datetime.now(UTC)
        doc = VideoDocument(
            id=video_id,
            filename=sanitized,
            title=PurePath(sanitized).stem or sanitized,
            source=VideoSource.UPLOAD,
            source_url=None,
            storage_path=str(final_path),
            thumbnail_path=str(thumbnail_path),
            duration_sec=probed.duration_sec,
            file_size_bytes=total_bytes,
            container=container,
            content_hash=content_hash,
            status=VideoStatus.IMPORTED,
            error_code=None,
            error_message=None,
            created_at=now,
            updated_at=now,
        )
        return await repo.insert(doc)

    except Exception:
        _cleanup_paths(temp_path, final_path, thumbnail_path, final_dir)
        raise


async def list_videos(
    *,
    repo: VideoRepository,
    status: VideoStatus | None,
) -> list[VideoDocument]:
    return await repo.list_videos(status=status)


async def delete_video(
    *,
    video_id: str,
    repo: VideoRepository,
) -> None:
    existing = await repo.get_by_id(video_id)
    if existing is None:
        raise VideoNotFoundError(f"video {video_id} not found")
    await repo.delete(video_id)
    _delete_video_files(existing)


def _delete_video_files(doc: VideoDocument) -> None:
    if doc.thumbnail_path:
        try:
            Path(doc.thumbnail_path).unlink(missing_ok=True)
        except OSError as exc:
            log.warning("thumbnail_delete_failed", path=doc.thumbnail_path, error=str(exc))
    if doc.storage_path:
        storage = Path(doc.storage_path)
        parent = storage.parent
        try:
            storage.unlink(missing_ok=True)
        except OSError as exc:
            log.warning("source_delete_failed", path=str(storage), error=str(exc))
        if parent.exists() and not any(parent.iterdir()):
            try:
                parent.rmdir()
            except OSError as exc:
                log.warning("dir_cleanup_failed", path=str(parent), error=str(exc))


async def import_from_url(
    *,
    url: str,
    repo: VideoRepository,
    settings: Settings,
) -> VideoDocument:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.hostname:
        raise InvalidUrlError(f"could not parse URL: {url}")
    if parsed.hostname not in settings.allowed_url_hosts:
        raise UnsupportedHostError(f"host '{parsed.hostname}' is not allowed; YouTube only")

    video_id = str(ObjectId())
    now = datetime.now(UTC)
    placeholder = VideoDocument(
        id=video_id,
        filename="",
        title=url,
        source=VideoSource.YOUTUBE,
        source_url=url,
        storage_path="",
        thumbnail_path=None,
        duration_sec=None,
        file_size_bytes=0,
        container=None,
        content_hash=None,
        status=VideoStatus.UPLOADING,
        error_code=None,
        error_message=None,
        created_at=now,
        updated_at=now,
    )
    return await repo.insert(placeholder)
