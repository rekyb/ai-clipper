"""Download Whisper large-v3 for export-time precise caption re-transcription.

Run: uv run python -m scripts.download_whisper_large
Only required before Phase 5 (export).
"""

import sys

from app.core.config import get_settings
from app.core.logging.setup import configure_logging, get_logger

WHISPER_LARGE_REPO = "Systran/faster-whisper-large-v3"


def download() -> int:
    configure_logging()
    log = get_logger("download_whisper_large")
    settings = get_settings()

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        log.error("hub_missing", hint="Install AI extras: uv sync --extra ai")
        return 2

    target = settings.whisper_large_v3_path
    if target.exists() and any(target.iterdir()):
        log.info("already_present", path=str(target))
        return 0

    log.info("downloading", repo=WHISPER_LARGE_REPO, target=str(target))
    snapshot_download(
        repo_id=WHISPER_LARGE_REPO,
        local_dir=str(target),
        local_dir_use_symlinks=False,
    )
    log.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(download())
