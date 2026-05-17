from enum import StrEnum


class WorkerErrorCode(StrEnum):
    TRANSCRIPTION_FAILED = "TRANSCRIPTION_FAILED"
    AUDIO_DECODE_FAILED = "AUDIO_DECODE_FAILED"
    VRAM_UNAVAILABLE = "VRAM_UNAVAILABLE"
    TRANSCRIPTION_TIMEOUT = "TRANSCRIPTION_TIMEOUT"


class TranscriptionDomainError(Exception):
    code: str = "INVALID_INPUT"
    http_status: int = 400


class TranscriptNotFoundError(TranscriptionDomainError):
    code = "NOT_FOUND"
    http_status = 404


class InvalidTranscriptionTransitionError(TranscriptionDomainError):
    code = "INVALID_TRANSITION"
    http_status = 409


class TranscriptionFailedError(TranscriptionDomainError):
    code = WorkerErrorCode.TRANSCRIPTION_FAILED.value
    http_status = 500


class AudioDecodeFailedError(TranscriptionDomainError):
    code = WorkerErrorCode.AUDIO_DECODE_FAILED.value
    http_status = 500


class TranscriptionTimeoutError(TranscriptionDomainError):
    code = WorkerErrorCode.TRANSCRIPTION_TIMEOUT.value
    http_status = 500
