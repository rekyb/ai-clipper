import importlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.gpu import vram
from app.core.logging.setup import get_logger

log = get_logger("models.loader")

_CUDA_DLL_DIRS_REGISTERED = False


def _register_cuda_dll_dirs() -> None:
    # NVIDIA pip wheels (nvidia-cuda-runtime-cu12, nvidia-cublas-cu12,
    # nvidia-cudnn-cu12) ship Windows DLLs under
    # .venv/Lib/site-packages/nvidia/{cuda_runtime,cublas,cudnn}/bin. CTranslate2
    # cannot find them unless we add each directory via os.add_dll_directory
    # before importing faster_whisper.
    global _CUDA_DLL_DIRS_REGISTERED
    if _CUDA_DLL_DIRS_REGISTERED or sys.platform != "win32":
        return
    for package in ("nvidia.cuda_runtime", "nvidia.cublas", "nvidia.cudnn"):
        try:
            mod = importlib.import_module(package)
        except ImportError as exc:
            log.warning("cuda_dll_dir_skipped", package=package, reason=str(exc))
            continue
        # nvidia.* are PEP 420 namespace packages: __file__ is None and the
        # package roots live in __path__. Fall back to __file__'s parent for
        # ordinary packages.
        roots: list[Path] = []
        ns_path = getattr(mod, "__path__", None)
        if ns_path:
            roots.extend(Path(p) for p in ns_path)
        elif mod.__file__ is not None:
            roots.append(Path(mod.__file__).parent)
        if not roots:
            log.warning(
                "cuda_dll_dir_skipped",
                package=package,
                reason="no __path__ or __file__ on module",
            )
            continue
        registered_any = False
        for root in roots:
            bin_dir = root / "bin"
            if not bin_dir.exists():
                continue
            try:
                os.add_dll_directory(str(bin_dir))
            except OSError as exc:
                log.error(
                    "cuda_dll_dir_registration_failed",
                    package=package,
                    path=str(bin_dir),
                    error=str(exc),
                )
                continue
            # add_dll_directory governs the top-level LoadLibrary call only;
            # transitive deps (e.g. cublas64_12 → cudart64_12) use the standard
            # Windows search order, which honors PATH. Prepend so cuBLAS can
            # find cuDART when it lazy-loads at first GPU op.
            bin_str = str(bin_dir)
            path_entries = os.environ.get("PATH", "").split(os.pathsep)
            if bin_str not in path_entries:
                os.environ["PATH"] = bin_str + os.pathsep + os.environ.get("PATH", "")
            log.info("cuda_dll_dir_registered", package=package, path=bin_str)
            registered_any = True
        if not registered_any:
            log.warning(
                "cuda_dll_dir_skipped",
                package=package,
                reason="bin directory missing under all roots",
                roots=[str(r) for r in roots],
            )
    _CUDA_DLL_DIRS_REGISTERED = True


class ModelNotInstalledError(RuntimeError):
    pass


class WhisperLoadError(RuntimeError):
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


def _load_whisper_model(*, path: Path, compute_type: str, device_index: int) -> Any:
    _register_cuda_dll_dirs()
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        log.exception(
            "whisper_import_failed",
            path=str(path),
            hint="install with: uv sync --extra whisper",
            error=str(exc),
        )
        raise WhisperLoadError("faster_whisper not importable") from exc

    try:
        return WhisperModel(
            model_size_or_path=str(path),
            device="cuda",
            compute_type=compute_type,
            device_index=device_index,
        )
    except Exception as exc:
        log.exception(
            "whisper_model_load_failed",
            path=str(path),
            compute_type=compute_type,
            device_index=device_index,
            exc_type=type(exc).__name__,
            error=str(exc),
        )
        raise WhisperLoadError(str(exc)) from exc


def load_whisper_medium() -> WhisperHandle:
    settings = get_settings()
    path = settings.whisper_medium_path
    _ensure_path(path, "Whisper medium")
    try:
        vram.assert_available(
            settings.whisper_vram_budget_bytes,
            safety_margin_bytes=settings.vram_safety_margin_bytes,
            skip=settings.skip_vram_guard,
        )
    except vram.VRAMUnavailableError as exc:
        log.warning(
            "whisper_vram_unavailable",
            requested_bytes=exc.requested_bytes,
            available_bytes=exc.available_bytes,
        )
        raise
    try:
        model = _load_whisper_model(
            path=path,
            compute_type=settings.whisper_compute_type,
            device_index=int(settings.cuda_visible_devices),
        )
    except WhisperLoadError:
        # _load_whisper_model already logged the structured failure.
        raise
    log.info("whisper_medium_loaded", path=str(path))
    return WhisperHandle(name="whisper-medium", path=path, model=model)


def load_whisper_large_v3() -> WhisperHandle:
    settings = get_settings()
    path = settings.whisper_large_v3_path
    _ensure_path(path, "Whisper large-v3")
    log.info("whisper_large_v3_stub", path=str(path))
    return WhisperHandle(name="whisper-large-v3", path=path)


def load_llama_8b() -> LlamaHandle:
    settings = get_settings()
    path = settings.llama_model_path
    _ensure_path(path, "Llama 3.1 8B Q5_K_M")
    log.info("llama_stub", path=str(path))
    return LlamaHandle(name="llama-3.1-8b-q5", path=path)
