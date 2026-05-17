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
    if "not available in your country" in msg or "geo" in msg:
        return YoutubeDownloadError(str(exc), code="VIDEO_REGION_BLOCKED")
    return YoutubeDownloadError(str(exc), code="DOWNLOAD_FAILED")


def download_to(url: str, target_dir: Path) -> YoutubeResult:
    target_dir.mkdir(parents=True, exist_ok=True)
    opts: dict[str, Any] = {
        "format": "best[ext=mp4]/best",
        "outtmpl": str(target_dir / "%(id)s.%(ext)s"),
        "noprogress": True,
        "quiet": True,
        "no_warnings": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
    except DownloadError as exc:
        raise _map_download_error(exc) from exc

    title = str(info.get("title") or info.get("id") or "untitled")
    return YoutubeResult(filename=Path(filename), title=title, source_url=url)
