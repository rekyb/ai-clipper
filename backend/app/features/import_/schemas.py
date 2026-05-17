from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.core.schemas.video_status import VideoStatus


class VideoSource(StrEnum):
    UPLOAD = "upload"
    YOUTUBE = "youtube"


class VideoDocument(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str = Field(validation_alias="_id", serialization_alias="id")
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
    last_progress_percent: int | None = Field(default=None, alias="lastProgressPercent")
    transcription_started_at: datetime | None = Field(default=None, alias="transcriptionStartedAt")
    transcription_finished_at: datetime | None = Field(
        default=None, alias="transcriptionFinishedAt"
    )
    restarted_at: datetime | None = Field(default=None, alias="restartedAt")


class UrlImportRequest(BaseModel):
    url: HttpUrl


class VideoListResponse(BaseModel):
    videos: list[VideoDocument]
