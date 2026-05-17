from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from yt_dlp.utils import DownloadError

from app.features.import_.youtube import YoutubeDownloadError, download_to


class _FakeYDL:
    def __init__(self, opts: dict[str, Any]) -> None:
        self.opts = opts

    def __enter__(self) -> "_FakeYDL":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def extract_info(self, _url: str, **_kwargs: Any) -> dict[str, Any]:
        return {"id": "dQw4w9WgXcQ", "title": "Never Gonna Give You Up", "ext": "mp4"}

    def prepare_filename(self, info: dict[str, Any]) -> str:
        return str(Path(self.opts["outtmpl"]).parent / f"{info['id']}.{info['ext']}")


def test_download_to_returns_filename_title_url(tmp_path: Path) -> None:
    with patch("app.features.import_.youtube.yt_dlp.YoutubeDL", _FakeYDL):
        result = download_to("https://youtu.be/dQw4w9WgXcQ", tmp_path)
    assert result.title == "Never Gonna Give You Up"
    assert result.filename == tmp_path / "dQw4w9WgXcQ.mp4"
    assert result.source_url == "https://youtu.be/dQw4w9WgXcQ"


def test_download_to_creates_target_dir(tmp_path: Path) -> None:
    nested = tmp_path / "deeply" / "nested"
    with patch("app.features.import_.youtube.yt_dlp.YoutubeDL", _FakeYDL):
        download_to("https://youtu.be/x", nested)
    assert nested.exists()


@pytest.mark.parametrize(
    ("message", "expected_code"),
    [
        ("ERROR: [youtube] x: Private video. Sign in.", "VIDEO_PRIVATE"),
        ("ERROR: [youtube] x: Video unavailable", "VIDEO_REMOVED"),
        ("ERROR: [youtube] x: This video has been removed", "VIDEO_REMOVED"),
        ("ERROR: [youtube] x: Sign in to confirm your age", "VIDEO_AGE_GATED"),
        ("ERROR: [youtube] x: This video is age-restricted", "VIDEO_AGE_GATED"),
        ("ERROR: [youtube] x: not available in your country", "VIDEO_REGION_BLOCKED"),
        ("ERROR: [youtube] x: geo-restricted to JP", "VIDEO_REGION_BLOCKED"),
        ("ERROR: [youtube] x: something else broke", "DOWNLOAD_FAILED"),
    ],
)
def test_download_error_messages_map_to_codes(
    tmp_path: Path, message: str, expected_code: str
) -> None:
    class _Failing:
        def __init__(self, _opts: dict[str, Any]) -> None: ...
        def __enter__(self) -> "_Failing":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def extract_info(self, *_: object, **__: object) -> dict[str, Any]:
            raise DownloadError(message)

        def prepare_filename(self, *_: object) -> str:
            return ""

    with patch("app.features.import_.youtube.yt_dlp.YoutubeDL", _Failing):
        with pytest.raises(YoutubeDownloadError) as exc_info:
            download_to("https://youtu.be/x", tmp_path)
    assert exc_info.value.code == expected_code
