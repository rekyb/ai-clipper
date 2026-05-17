import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import structlog

from app.core.schemas.video_status import VideoStatus
from app.features.import_.repository import VideoRepository

log = structlog.get_logger("import.cleanup")


def sweep_stale_temp_files(originals_dir: Path, max_age_hours: float = 1.0) -> int:
    tmp_dir = originals_dir / ".tmp"
    if not tmp_dir.exists():
        return 0
    cutoff = time.time() - (max_age_hours * 3600)
    removed = 0
    for entry in tmp_dir.iterdir():
        try:
            mtime = entry.stat().st_mtime
        except FileNotFoundError:
            continue
        if mtime >= cutoff:
            continue
        try:
            if entry.is_dir():
                _rmtree_safe(entry)
            else:
                entry.unlink()
            removed += 1
        except OSError as exc:
            log.warning("tmp_cleanup_failed", path=str(entry), error=str(exc))
    return removed


async def mark_stale_uploading_as_failed(repo: VideoRepository, max_age_hours: float = 1.0) -> int:
    cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
    stuck = [
        doc
        for doc in await repo.list_videos(status=VideoStatus.UPLOADING)
        if doc.updated_at < cutoff
    ]
    for doc in stuck:
        await repo.update_status(
            doc.id,
            status=VideoStatus.FAILED,
            error_code="INTERRUPTED",
            error_message="import was interrupted (likely backend restart)",
        )
    return len(stuck)


def _rmtree_safe(path: Path) -> None:
    import shutil

    shutil.rmtree(path, ignore_errors=True)
