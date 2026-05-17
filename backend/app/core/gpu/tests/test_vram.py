from unittest.mock import patch

import pytest

from app.core.gpu import vram


def test_vram_unavailable_error_carries_requested_and_available_bytes() -> None:
    err = vram.VRAMUnavailableError(requested_bytes=2_500_000_000, available_bytes=1_000_000_000)
    assert err.requested_bytes == 2_500_000_000
    assert err.available_bytes == 1_000_000_000
    assert "2.3 GB" in str(err) or "2.5 GB" in str(err)
    assert "1.0 GB" in str(err) or "0.9 GB" in str(err)


def test_assert_available_passes_when_free_exceeds_required_plus_margin() -> None:
    fake_snapshot = vram.GpuSnapshot(
        free_bytes=4_000_000_000, used_bytes=2_000_000_000, total_bytes=6_000_000_000
    )
    with (
        patch.object(vram, "_HAS_PYNVML", True),
        patch.object(vram, "snapshot", return_value=fake_snapshot),
    ):
        vram.assert_available(required_bytes=2_000_000_000, safety_margin_bytes=300_000_000)


def test_assert_available_raises_when_free_below_required_plus_margin() -> None:
    fake_snapshot = vram.GpuSnapshot(
        free_bytes=2_100_000_000, used_bytes=4_000_000_000, total_bytes=6_100_000_000
    )
    with (
        patch.object(vram, "_HAS_PYNVML", True),
        patch.object(vram, "snapshot", return_value=fake_snapshot),
        pytest.raises(vram.VRAMUnavailableError) as exc_info,
    ):
        vram.assert_available(required_bytes=2_000_000_000, safety_margin_bytes=300_000_000)
    assert exc_info.value.requested_bytes == 2_300_000_000
    assert exc_info.value.available_bytes == 2_100_000_000


def test_assert_available_is_no_op_when_skip_flag_set() -> None:
    fake_snapshot = vram.GpuSnapshot(free_bytes=0, used_bytes=0, total_bytes=0)
    with patch.object(vram, "snapshot", return_value=fake_snapshot):
        vram.assert_available(required_bytes=2_000_000_000, safety_margin_bytes=0, skip=True)


def test_assert_available_is_no_op_when_pynvml_missing() -> None:
    with patch.object(vram, "_HAS_PYNVML", False):
        vram.assert_available(required_bytes=10_000_000_000_000, safety_margin_bytes=0)


def test_snapshot_raises_runtime_error_when_pynvml_missing() -> None:
    with patch.object(vram, "_HAS_PYNVML", False), pytest.raises(RuntimeError, match="pynvml"):
        vram.snapshot()


def test_assert_available_boundary_pass_when_free_exactly_equals_needed() -> None:
    fake_snapshot = vram.GpuSnapshot(
        free_bytes=2_300_000_000, used_bytes=0, total_bytes=8_000_000_000
    )
    with (
        patch.object(vram, "_HAS_PYNVML", True),
        patch.object(vram, "snapshot", return_value=fake_snapshot),
    ):
        vram.assert_available(required_bytes=2_000_000_000, safety_margin_bytes=300_000_000)


def test_gpu_snapshot_is_immutable() -> None:
    snap = vram.GpuSnapshot(free_bytes=1, used_bytes=2, total_bytes=3)
    with pytest.raises(AttributeError):
        snap.free_bytes = 99  # type: ignore[misc]
