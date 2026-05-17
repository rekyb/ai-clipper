from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class VideoStatus(StrEnum):
    UPLOADING = "uploading"
    IMPORTED = "imported"
    FAILED = "failed"


class VideoSource(StrEnum):
    UPLOAD = "upload"
    YOUTUBE = "youtube"


class VideoDocument(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str = Field(default="", alias="_id")
    filename: str
    title: str
    source: VideoSource
    source_url: str | None = Field(default=None, alias="sourceUrl")
    storage_path: str = Field(alias="storagePath")
    thumbnail_path: str | None = Field(default=None, alias="thumbnailPath")
    duration_sec: float | None = Field(default=None, alias="durationSec")
    file_size_bytes: int = Field(alias="fileSizeBytes")
    container: str | None = None
    content_hash: str | None = Field(default=None, alias="contentHash")
    status: VideoStatus
    error_code: str | None = Field(default=None, alias="errorCode")
    error_message: str | None = Field(default=None, alias="errorMessage")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class UrlImportRequest(BaseModel):
    url: HttpUrl


class VideoListResponse(BaseModel):
    videos: list[VideoDocument]
