import pytest

from app.core.config import Settings


def test_default_whisper_vram_budget_is_2200_mb() -> None:
    s = Settings(_env_file=None)
    assert s.whisper_vram_budget_mb == 2200
    assert s.whisper_vram_budget_bytes == 2200 * 1024 * 1024


def test_default_vram_safety_margin_is_300_mb() -> None:
    s = Settings(_env_file=None)
    assert s.vram_safety_margin_mb == 300
    assert s.vram_safety_margin_bytes == 300 * 1024 * 1024


def test_default_skip_vram_guard_is_false() -> None:
    s = Settings(_env_file=None)
    assert s.skip_vram_guard is False


def test_default_transcription_poll_interval_is_two_seconds() -> None:
    s = Settings(_env_file=None)
    assert s.transcription_poll_interval_sec == pytest.approx(2.0)


def test_default_transcription_timeout_multiplier_is_four() -> None:
    s = Settings(_env_file=None)
    assert s.transcription_timeout_multiplier == pytest.approx(4.0)


def test_default_transcription_progress_throttle_is_one_second() -> None:
    s = Settings(_env_file=None)
    assert s.transcription_progress_throttle_sec == pytest.approx(1.0)


def test_env_override_for_vram_budget() -> None:
    s = Settings(_env_file=None, whisper_vram_budget_mb=4096)
    assert s.whisper_vram_budget_mb == 4096
    assert s.whisper_vram_budget_bytes == 4096 * 1024 * 1024


def test_env_override_for_skip_vram_guard() -> None:
    s = Settings(_env_file=None, skip_vram_guard=True)
    assert s.skip_vram_guard is True


def test_env_override_for_timeout_multiplier() -> None:
    s = Settings(_env_file=None, transcription_timeout_multiplier=6.0)
    assert s.transcription_timeout_multiplier == pytest.approx(6.0)
