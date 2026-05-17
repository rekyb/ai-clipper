"""Model loader stubs.

Phase 1: contract + path validation only. No actual loading.
Phase 2 wires faster-whisper (Whisper medium) and Phase 3 wires llama-cpp-python.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.logging.setup import get_logger

log = get_logger("models.loader")


class ModelNotInstalledError(RuntimeError):
    pass


@dataclass(frozen=True)
class WhisperHandle:
    name: str
    path: Path
    model: Any = None


@dataclass(frozen=True)
class LlamaHandle:
    name: str
    path: Path
    model: Any = None


def _ensure_path(path: Path, label: str) -> None:
    if not path.exists():
        raise ModelNotInstalledError(
            f"{label} not found at {path}. Run: uv run python -m scripts.download_models"
        )


def load_whisper_medium() -> WhisperHandle:
    """Wire faster-whisper here in Phase 2.

    from faster_whisper import WhisperModel
    return WhisperHandle(name=..., path=..., model=WhisperModel(...))
    """
    settings = get_settings()
    path = settings.whisper_medium_path
    _ensure_path(path, "Whisper medium")
    log.info("whisper_medium_stub", path=str(path))
    return WhisperHandle(name="whisper-medium", path=path)


def load_whisper_large_v3() -> WhisperHandle:
    """Lazy-loaded for export caption pass (Phase 5)."""
    settings = get_settings()
    path = settings.whisper_large_v3_path
    _ensure_path(path, "Whisper large-v3")
    log.info("whisper_large_v3_stub", path=str(path))
    return WhisperHandle(name="whisper-large-v3", path=path)


def load_llama_8b() -> LlamaHandle:
    """Wire llama-cpp-python here in Phase 3.

    from llama_cpp import Llama
    return LlamaHandle(name=..., path=..., model=Llama(model_path=str(path), ...))
    """
    settings = get_settings()
    path = settings.llama_model_path
    _ensure_path(path, "Llama 3.1 8B Q5_K_M")
    log.info("llama_stub", path=str(path))
    return LlamaHandle(name="llama-3.1-8b-q5", path=path)
