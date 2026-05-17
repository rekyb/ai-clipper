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


def test_download_to_forwards_browser_cookies_simple(tmp_path: Path) -> None:
    captured: dict[str, Any] = {}

    class _Capture(_FakeYDL):
        def __init__(self, opts: dict[str, Any]) -> None:
            super().__init__(opts)
            captured.update(opts)

    with patch("app.features.import_.youtube.yt_dlp.YoutubeDL", _Capture):
        download_to("https://youtu.be/x", tmp_path, cookies_from_browser="chrome")
    assert captured.get("cookiesfrombrowser") == ("chrome",)


def test_download_to_forwards_browser_cookies_with_profile(tmp_path: Path) -> None:
    captured: dict[str, Any] = {}

    class _Capture(_FakeYDL):
        def __init__(self, opts: dict[str, Any]) -> None:
            super().__init__(opts)
            captured.update(opts)

    with patch("app.features.import_.youtube.yt_dlp.YoutubeDL", _Capture):
        download_to("https://youtu.be/x", tmp_path, cookies_from_browser="chrome:Profile 1")
    assert captured.get("cookiesfrombrowser") == ("chrome", "Profile 1")


def test_download_to_forwards_cookies_file(tmp_path: Path) -> None:
    captured: dict[str, Any] = {}
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n")

    class _Capture(_FakeYDL):
        def __init__(self, opts: dict[str, Any]) -> None:
            super().__init__(opts)
            captured.update(opts)

    with patch("app.features.import_.youtube.yt_dlp.YoutubeDL", _Capture):
        download_to("https://youtu.be/x", tmp_path, cookies_file=cookies)
    assert captured.get("cookiefile") == str(cookies)


def test_download_to_omits_cookies_when_unset(tmp_path: Path) -> None:
    captured: dict[str, Any] = {}

    class _Capture(_FakeYDL):
        def __init__(self, opts: dict[str, Any]) -> None:
            super().__init__(opts)
            captured.update(opts)

    with patch("app.features.import_.youtube.yt_dlp.YoutubeDL", _Capture):
        download_to("https://youtu.be/x", tmp_path)
    assert "cookiesfrombrowser" not in captured
    assert "cookiefile" not in captured


def test_download_to_uses_dash_aware_format_selector(tmp_path: Path) -> None:
    # YouTube serves most modern videos as DASH (separate audio + video). The
    # selector must prefer the best DASH video+audio combo and merge to mp4,
    # falling back to a single combined stream when one exists.
    captured: dict[str, Any] = {}

    class _Capture(_FakeYDL):
        def __init__(self, opts: dict[str, Any]) -> None:
            super().__init__(opts)
            captured.update(opts)

    with patch("app.features.import_.youtube.yt_dlp.YoutubeDL", _Capture):
        download_to("https://youtu.be/x", tmp_path)
    fmt = captured.get("format", "")
    # Must include a separate-streams branch (bv*+ba) and an mp4 fallback.
    assert "bv*" in fmt or "bestvideo" in fmt
    assert "ba" in fmt or "bestaudio" in fmt
    # Forces ffmpeg to merge separate streams into a single mp4 file.
    assert captured.get("merge_output_format") == "mp4"


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
        ("ERROR: [youtube] x: Sign in to confirm you're not a bot", "VIDEO_AUTH_REQUIRED"),
        ("ERROR: [youtube] x: Use --cookies-from-browser", "VIDEO_AUTH_REQUIRED"),
        ("ERROR: [youtube] x: Requested format is not available", "VIDEO_FORMAT_UNAVAILABLE"),
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
