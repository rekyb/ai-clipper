import pytest

from app.core.models.loader import (
    ModelNotInstalledError,
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


def test_llama_raises_when_missing(tmp_path, monkeypatch):
    from app.core import config

    config.get_settings.cache_clear()
    monkeypatch.setenv("MODELS_DIR", str(tmp_path))

    with pytest.raises(ModelNotInstalledError):
        load_llama_8b()

    config.get_settings.cache_clear()
