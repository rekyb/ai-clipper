from dataclasses import dataclass

try:
    import pynvml

    _HAS_PYNVML = True
except ImportError:
    _HAS_PYNVML = False


@dataclass(frozen=True)
class GpuSnapshot:
    free_bytes: int
    used_bytes: int
    total_bytes: int


class VRAMUnavailableError(RuntimeError):
    def __init__(self, requested_bytes: int, available_bytes: int) -> None:
        self.requested_bytes = requested_bytes
        self.available_bytes = available_bytes
        super().__init__(
            f"Requested {_human(requested_bytes)} VRAM but only {_human(available_bytes)} available"
        )


def _human(num_bytes: int) -> str:
    gb = num_bytes / (1024**3)
    return f"{gb:.1f} GB"


_nvml_initialized = False


def _ensure_nvml() -> None:
    global _nvml_initialized
    if _nvml_initialized:
        return
    pynvml.nvmlInit()
    _nvml_initialized = True


def snapshot(device_index: int = 0) -> GpuSnapshot:
    if not _HAS_PYNVML:
        raise RuntimeError("pynvml is not installed; GPU monitoring unavailable")
    _ensure_nvml()
    handle = pynvml.nvmlDeviceGetHandleByIndex(device_index)
    info = pynvml.nvmlDeviceGetMemoryInfo(handle)
    return GpuSnapshot(free_bytes=info.free, used_bytes=info.used, total_bytes=info.total)


def assert_available(
    required_bytes: int,
    *,
    safety_margin_bytes: int = 0,
    skip: bool = False,
    device_index: int = 0,
) -> None:
    if skip or not _HAS_PYNVML:
        return
    snap = snapshot(device_index)
    needed = required_bytes + safety_margin_bytes
    if snap.free_bytes < needed:
        raise VRAMUnavailableError(requested_bytes=needed, available_bytes=snap.free_bytes)
