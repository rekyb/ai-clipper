from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.schemas.video_status import VideoStatus


class Word(BaseModel):
    word: str
    start: float
    end: float
    probability: float


class Segment(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    start: float
    end: float
    text: str
    avg_logprob: float = Field(alias="avgLogprob")
    no_speech_prob: float = Field(alias="noSpeechProb")
    words: list[Word]


class TranscriptDocument(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str = Field(validation_alias="_id", serialization_alias="id")
    video_id: str = Field(alias="videoId")
    language: str
    language_probability: float = Field(alias="languageProbability")
    duration_sec: float = Field(alias="durationSec")
    model_name: str = Field(alias="modelName")
    model_version: str = Field(alias="modelVersion")
    segments: list[Segment]
    created_at: datetime = Field(alias="createdAt")


ProgressEventType = Literal["snapshot", "progress", "complete", "error"]
ProgressStage = Literal["transcription"]


class ProgressEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: ProgressEventType
    video_id: str = Field(alias="videoId")
    status: VideoStatus
    percent: int
    stage: ProgressStage
    segments_done: int | None = Field(default=None, alias="segmentsDone")
    segments_total: int | None = Field(default=None, alias="segmentsTotal")
    elapsed_sec: float = Field(alias="elapsedSec")
    eta_sec: float | None = Field(default=None, alias="etaSec")
    queue_position: int | None = Field(default=None, alias="queuePosition")
    error_code: str | None = Field(default=None, alias="errorCode")
    error_message: str | None = Field(default=None, alias="errorMessage")


class RetryResponse(BaseModel):
    id: str
    status: VideoStatus
