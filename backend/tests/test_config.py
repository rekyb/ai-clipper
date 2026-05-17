from pathlib import Path

import pytest

from app.core.config import Settings


def test_defaults_are_within_prd_caps() -> None:
    settings = Settings(_env_file=None)
    assert settings.max_file_size_bytes == 5 * 1024**3
    assert settings.max_duration_seconds == 14400


def test_default_supported_containers() -> None:
    settings = Settings(_env_file=None)
    assert settings.supported_containers == ["mp4", "mkv", "mov", "avi", "webm"]


def test_default_allowed_url_hosts() -> None:
    settings = Settings(_env_file=None)
    assert "youtube.com" in settings.allowed_url_hosts
    assert "youtu.be" in settings.allowed_url_hosts
    assert "www.youtube.com" in settings.allowed_url_hosts
    assert "m.youtube.com" in settings.allowed_url_hosts


def test_thumbnails_dir_is_under_media_dir(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, media_dir=tmp_path)
    assert settings.thumbnails_dir == tmp_path / "thumbnails"


def test_max_file_size_bytes_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_FILE_SIZE_BYTES", "1024")
    settings = Settings(_env_file=None)
    assert settings.max_file_size_bytes == 1024


def test_max_duration_seconds_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_DURATION_SECONDS", "600")
    settings = Settings(_env_file=None)
    assert settings.max_duration_seconds == 600


def test_supported_containers_env_override_comma_separated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPPORTED_CONTAINERS", "mp4, webm")
    settings = Settings(_env_file=None)
    assert settings.supported_containers == ["mp4", "webm"]


def test_allowed_url_hosts_env_override_comma_separated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALLOWED_URL_HOSTS", "youtube.com, youtu.be")
    settings = Settings(_env_file=None)
    assert settings.allowed_url_hosts == ["youtube.com", "youtu.be"]


def test_cors_origins_env_override_comma_separated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://a.com, http://b.com")
    settings = Settings(_env_file=None)
    assert settings.cors_origins == ["http://a.com", "http://b.com"]
