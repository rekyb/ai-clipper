import os
import sys
from unittest.mock import patch

import pytest
from structlog.testing import capture_logs

from app.core.models.loader import (
    ModelNotInstalledError,
    WhisperLoadError,
    _load_whisper_model,
    _register_cuda_dll_dirs,
    load_llama_8b,
    load_whisper_medium,
)


def test_whisper_medium_raises_when_missing(tmp_path, monkeypatch):
    from app.core import config

    config.get_settings.cache_clear()
    monkeypatch.setenv("MODELS_DIR", str(tmp_path))

    with pytest.raises(ModelNotInstalledError) as exc:
        load_whisper_medium()
    assert "download_models" in str(exc.value)

    config.get_settings.cache_clear()


def test_whisper_medium_asserts_vram_before_constructing_model(tmp_path, monkeypatch):
    from app.core import config
    from app.core.gpu import vram

    # Stage a fake model directory so _ensure_path passes.
    whisper_dir = tmp_path / "whisper-medium"
    whisper_dir.mkdir()
    (whisper_dir / "model.bin").write_bytes(b"")

    config.get_settings.cache_clear()
    monkeypatch.setenv("MODELS_DIR", str(tmp_path))

    with (
        patch.object(vram, "_HAS_PYNVML", True),
        patch.object(
            vram,
            "snapshot",
            return_value=vram.GpuSnapshot(free_bytes=100, used_bytes=0, total_bytes=8 * 1024**3),
        ),
        pytest.raises(vram.VRAMUnavailableError),
    ):
        load_whisper_medium()

    config.get_settings.cache_clear()


def test_whisper_medium_constructs_model_when_vram_available(tmp_path, monkeypatch):
    from app.core import config, models
    from app.core.gpu import vram

    whisper_dir = tmp_path / "whisper-medium"
    whisper_dir.mkdir()
    (whisper_dir / "model.bin").write_bytes(b"")

    config.get_settings.cache_clear()
    monkeypatch.setenv("MODELS_DIR", str(tmp_path))

    fake_model = object()
    fake_factory = lambda **_: fake_model  # noqa: E731

    with (
        patch.object(vram, "_HAS_PYNVML", True),
        patch.object(
            vram,
            "snapshot",
            return_value=vram.GpuSnapshot(
                free_bytes=4 * 1024**3, used_bytes=0, total_bytes=8 * 1024**3
            ),
        ),
        patch.object(models.loader, "_load_whisper_model", fake_factory),
    ):
        handle = load_whisper_medium()

    assert handle.model is fake_model
    assert handle.name == "whisper-medium"
    config.get_settings.cache_clear()


def test_load_whisper_model_wraps_runtime_failure_with_context(tmp_path):
    fake_module = type(sys)("faster_whisper")

    class _BoomModel:
        def __init__(self, **kwargs):
            raise RuntimeError("Library cublas64_12.dll is not found or cannot be loaded")

    fake_module.WhisperModel = _BoomModel
    with patch.dict(sys.modules, {"faster_whisper": fake_module}):
        with capture_logs() as logs:
            with pytest.raises(WhisperLoadError) as exc:
                _load_whisper_model(path=tmp_path, compute_type="float16", device_index=0)

    assert "cublas64_12.dll" in str(exc.value)
    assert exc.value.__cause__ is not None
    assert isinstance(exc.value.__cause__, RuntimeError)

    failure_logs = [e for e in logs if e.get("event") == "whisper_model_load_failed"]
    assert failure_logs, f"expected whisper_model_load_failed log, got {logs}"
    entry = failure_logs[0]
    assert entry["compute_type"] == "float16"
    assert entry["device_index"] == 0
    assert entry["exc_type"] == "RuntimeError"


def test_load_whisper_model_wraps_import_failure(tmp_path):
    # If faster_whisper itself can't be imported (e.g., missing wheel), surface
    # WhisperLoadError with the import error preserved as __cause__.
    with patch.dict(sys.modules, {"faster_whisper": None}):
        with capture_logs() as logs:
            with pytest.raises(WhisperLoadError):
                _load_whisper_model(path=tmp_path, compute_type="float16", device_index=0)

    import_logs = [e for e in logs if e.get("event") == "whisper_import_failed"]
    assert import_logs, f"expected whisper_import_failed log, got {logs}"


def test_register_cuda_dll_dirs_uses_namespace_package_path(monkeypatch, tmp_path):
    # nvidia-cublas-cu12 etc. install as PEP 420 namespace packages: __file__
    # is None, but __path__ points to the package directory. The registrar must
    # walk __path__ entries and add their bin/ subdirs.
    from app.core.models import loader

    monkeypatch.setattr(loader, "_CUDA_DLL_DIRS_REGISTERED", False)
    monkeypatch.setattr(loader.sys, "platform", "win32")

    cublas_dir = tmp_path / "cublas"
    (cublas_dir / "bin").mkdir(parents=True)
    (cublas_dir / "bin" / "cublas64_12.dll").write_bytes(b"")

    class _NamespaceStub:
        __file__ = None
        __path__: list[str] = [str(cublas_dir)]  # noqa: RUF012  test double mimicking namespace pkg

    def fake_import(name: str):
        if name == "nvidia.cublas":
            return _NamespaceStub()
        raise ImportError(name)

    added: list[str] = []
    monkeypatch.setattr(loader.importlib, "import_module", fake_import)
    monkeypatch.setattr(loader.os, "add_dll_directory", lambda p: added.append(p) or None)

    with capture_logs() as logs:
        _register_cuda_dll_dirs()

    assert str(cublas_dir / "bin") in added, f"expected cublas bin dir to be registered, got {added}"
    registered = [
        e
        for e in logs
        if e.get("event") == "cuda_dll_dir_registered" and e.get("package") == "nvidia.cublas"
    ]
    assert registered, f"expected cuda_dll_dir_registered for cublas, got {logs}"


def test_register_cuda_dll_dirs_prepends_bin_dirs_to_path(monkeypatch, tmp_path):
    # add_dll_directory does NOT propagate to transitive DLL loads (cublas
    # loading cudart, etc.). Prepending bin dirs to PATH covers that case.
    from app.core.models import loader

    monkeypatch.setattr(loader, "_CUDA_DLL_DIRS_REGISTERED", False)
    monkeypatch.setattr(loader.sys, "platform", "win32")

    cuda_runtime_dir = tmp_path / "cuda_runtime"
    cublas_dir = tmp_path / "cublas"
    for d in (cuda_runtime_dir, cublas_dir):
        (d / "bin").mkdir(parents=True)

    class _NsRuntime:
        __file__ = None
        __path__: list[str] = [str(cuda_runtime_dir)]  # noqa: RUF012

    class _NsCublas:
        __file__ = None
        __path__: list[str] = [str(cublas_dir)]  # noqa: RUF012

    stubs = {"nvidia.cuda_runtime": _NsRuntime(), "nvidia.cublas": _NsCublas()}

    def fake_import(name: str):
        if name in stubs:
            return stubs[name]
        raise ImportError(name)

    monkeypatch.setattr(loader.importlib, "import_module", fake_import)
    monkeypatch.setattr(loader.os, "add_dll_directory", lambda p: None)
    monkeypatch.setenv("PATH", "C:\\existing")

    _register_cuda_dll_dirs()

    new_path = os.environ["PATH"]
    parts = new_path.split(os.pathsep)
    assert str(cuda_runtime_dir / "bin") in parts
    assert str(cublas_dir / "bin") in parts
    # The original PATH must still be present.
    assert "C:\\existing" in parts
    # Bin dirs should appear BEFORE the original entries (prepended).
    assert parts.index(str(cuda_runtime_dir / "bin")) < parts.index("C:\\existing")


def test_register_cuda_dll_dirs_does_not_duplicate_path_entries(monkeypatch, tmp_path):
    from app.core.models import loader

    monkeypatch.setattr(loader, "_CUDA_DLL_DIRS_REGISTERED", False)
    monkeypatch.setattr(loader.sys, "platform", "win32")

    cublas_dir = tmp_path / "cublas"
    (cublas_dir / "bin").mkdir(parents=True)
    bin_path = str(cublas_dir / "bin")

    class _Ns:
        __file__ = None
        __path__: list[str] = [str(cublas_dir)]  # noqa: RUF012

    def fake_import(name: str):
        if name == "nvidia.cublas":
            return _Ns()
        raise ImportError(name)

    monkeypatch.setattr(loader.importlib, "import_module", fake_import)
    monkeypatch.setattr(loader.os, "add_dll_directory", lambda p: None)
    monkeypatch.setenv("PATH", f"{bin_path};C:\\existing")

    _register_cuda_dll_dirs()

    parts = os.environ["PATH"].split(os.pathsep)
    assert parts.count(bin_path) == 1


def test_register_cuda_dll_dirs_continues_past_failed_package(monkeypatch):
    from app.core.models import loader

    monkeypatch.setattr(loader, "_CUDA_DLL_DIRS_REGISTERED", False)
    monkeypatch.setattr(loader.sys, "platform", "win32")

    real_import = loader.importlib.import_module
    calls: list[str] = []

    def selective_import(name: str):
        calls.append(name)
        if name == "nvidia.cuda_runtime":
            raise ImportError("simulated missing wheel")
        # Return a module-like object with __file__=None so the bin/ check skips
        class _Stub:
            __file__ = None

        return _Stub()

    monkeypatch.setattr(loader.importlib, "import_module", selective_import)

    with capture_logs() as logs:
        _register_cuda_dll_dirs()

    # All three nvidia packages were attempted despite the first one failing.
    assert "nvidia.cuda_runtime" in calls
    assert "nvidia.cublas" in calls
    assert "nvidia.cudnn" in calls

    skip_logs = [
        e
        for e in logs
        if e.get("event") == "cuda_dll_dir_skipped" and e.get("package") == "nvidia.cuda_runtime"
    ]
    assert skip_logs, f"expected cuda_dll_dir_skipped for cuda_runtime, got {logs}"

    # restore real importlib for subsequent tests
    monkeypatch.setattr(loader.importlib, "import_module", real_import)


def test_llama_raises_when_missing(tmp_path, monkeypatch):
    from app.core import config

    config.get_settings.cache_clear()
    monkeypatch.setenv("MODELS_DIR", str(tmp_path))

    with pytest.raises(ModelNotInstalledError):
        load_llama_8b()

    config.get_settings.cache_clear()
