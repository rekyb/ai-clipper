"""Download Whisper medium + Llama 3.1 8B Q5_K_M into models/.

Run: uv run python -m scripts.download_models

Idempotent — skips files that already exist with the expected size.
Requires: huggingface-hub (pulled in transitively by faster-whisper / llama-cpp-python).
This script is Phase 1 infrastructure; full execution waits on the ai extras install:
    uv sync --extra ai
"""

import sys
from pathlib import Path

from app.core.config import get_settings
from app.core.logging.setup import configure_logging, get_logger

WHISPER_MEDIUM_REPO = "Systran/faster-whisper-medium"
LLAMA_REPO = "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF"
LLAMA_FILENAME = "Meta-Llama-3.1-8B-Instruct-Q5_K_M.gguf"


def download() -> int:
    configure_logging()
    log = get_logger("download_models")
    settings = get_settings()

    try:
        from huggingface_hub import hf_hub_download, snapshot_download
    except ImportError:
        log.error(
            "hub_missing",
            hint="Install AI extras: uv sync --extra ai",
        )
        return 2

    settings.models_dir.mkdir(parents=True, exist_ok=True)

    whisper_target = settings.whisper_medium_path
    if whisper_target.exists() and any(whisper_target.iterdir()):
        log.info("whisper_already_present", path=str(whisper_target))
    else:
        log.info("downloading_whisper", repo=WHISPER_MEDIUM_REPO, target=str(whisper_target))
        snapshot_download(
            repo_id=WHISPER_MEDIUM_REPO,
            local_dir=str(whisper_target),
            local_dir_use_symlinks=False,
        )
        log.info("whisper_downloaded")

    llama_target = settings.llama_model_path
    llama_target.parent.mkdir(parents=True, exist_ok=True)
    if llama_target.exists():
        log.info("llama_already_present", path=str(llama_target))
    else:
        log.info("downloading_llama", repo=LLAMA_REPO, file=LLAMA_FILENAME)
        downloaded = hf_hub_download(
            repo_id=LLAMA_REPO,
            filename=LLAMA_FILENAME,
            local_dir=str(llama_target.parent),
        )
        Path(downloaded).rename(llama_target)
        log.info("llama_downloaded", path=str(llama_target))

    log.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(download())
