from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yt_dlp
from yt_dlp.utils import DownloadError


class YoutubeDownloadError(Exception):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class YoutubeResult:
    filename: Path
    title: str
    source_url: str


def _map_download_error(exc: DownloadError) -> YoutubeDownloadError:
    msg = str(exc).lower()
    if "private video" in msg:
        return YoutubeDownloadError(str(exc), code="VIDEO_PRIVATE")
    if "has been removed" in msg or "video unavailable" in msg:
        return YoutubeDownloadError(str(exc), code="VIDEO_REMOVED")
    if "confirm your age" in msg or "age-restricted" in msg or "age restricted" in msg:
        return YoutubeDownloadError(str(exc), code="VIDEO_AGE_GATED")
    # YouTube's actual error string uses U+2019, not ASCII apostrophe.
    if (
        "confirm you're not a bot" in msg
        or "confirm you’re not a bot" in msg  # noqa: RUF001
        or "--cookies" in msg
    ):
        return YoutubeDownloadError(str(exc), code="VIDEO_AUTH_REQUIRED")
    if "not available in your country" in msg or "geo" in msg:
        return YoutubeDownloadError(str(exc), code="VIDEO_REGION_BLOCKED")
    if "requested format is not available" in msg:
        return YoutubeDownloadError(str(exc), code="VIDEO_FORMAT_UNAVAILABLE")
    return YoutubeDownloadError(str(exc), code="DOWNLOAD_FAILED")


def _parse_browser_spec(spec: str) -> tuple[str, ...]:
    # yt-dlp accepts ("chrome",) or ("chrome", "Profile 1"). The CLI form is
    # "chrome:Profile 1"; we split on the first colon only.
    name, sep, profile = spec.partition(":")
    if sep and profile:
        return (name.strip(), profile.strip())
    return (name.strip(),)


def download_to(
    url: str,
    target_dir: Path,
    *,
    cookies_from_browser: str | None = None,
    cookies_file: Path | None = None,
) -> YoutubeResult:
    target_dir.mkdir(parents=True, exist_ok=True)
    # YouTube serves modern uploads as DASH (separate audio + video). Order:
    #   1. mp4 video + m4a audio (no transcode, just remux)
    #   2. any best video + any best audio (transcoded to mp4 by ffmpeg)
    #   3. legacy single-stream mp4
    #   4. legacy single-stream anything
    # `merge_output_format` forces the merged file to land as .mp4.
    opts: dict[str, Any] = {
        "format": "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "outtmpl": str(target_dir / "%(id)s.%(ext)s"),
        "noprogress": True,
        "quiet": True,
        "no_warnings": True,
    }
    if cookies_from_browser:
        opts["cookiesfrombrowser"] = _parse_browser_spec(cookies_from_browser)
    if cookies_file:
        opts["cookiefile"] = str(cookies_file)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
    except DownloadError as exc:
        raise _map_download_error(exc) from exc

    title = str(info.get("title") or info.get("id") or "untitled")
    return YoutubeResult(filename=Path(filename), title=title, source_url=url)
