from enum import StrEnum


class VideoStatus(StrEnum):
    UPLOADING = "uploading"
    IMPORTED = "imported"
    QUEUED = "queued"
    TRANSCRIBING = "transcribing"
    READY = "ready"
    FAILED = "failed"
