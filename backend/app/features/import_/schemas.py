from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, HttpUrl


class VideoStatus(StrEnum):
    UPLOADING = "uploading"
    IMPORTED = "imported"
    FAILED = "failed"


class VideoSource(StrEnum):
    UPLOAD = "upload"
    YOUTUBE = "youtube"


class VideoDocument(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    title: str
    source: VideoSource
    source_url: str | None
    storage_path: str
    thumbnail_url: str | None
    duration_sec: float | None
    file_size_bytes: int
    container: str | None
    status: VideoStatus
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class UrlImportRequest(BaseModel):
    url: HttpUrl


class VideoListResponse(BaseModel):
    videos: list[VideoDocument]
