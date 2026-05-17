from app.features.transcription.errors import (
    AudioDecodeFailedError,
    InvalidTranscriptionTransitionError,
    TranscriptionDomainError,
    TranscriptionFailedError,
    TranscriptionTimeoutError,
    TranscriptNotFoundError,
    WorkerErrorCode,
)


def test_all_domain_errors_inherit_from_base() -> None:
    assert issubclass(TranscriptNotFoundError, TranscriptionDomainError)
    assert issubclass(InvalidTranscriptionTransitionError, TranscriptionDomainError)
    assert issubclass(TranscriptionFailedError, TranscriptionDomainError)
    assert issubclass(AudioDecodeFailedError, TranscriptionDomainError)
    assert issubclass(TranscriptionTimeoutError, TranscriptionDomainError)


def test_transcript_not_found_has_404_status() -> None:
    err = TranscriptNotFoundError("missing")
    assert err.http_status == 404
    assert err.code == "NOT_FOUND"


def test_invalid_transition_has_409_status() -> None:
    err = InvalidTranscriptionTransitionError("cannot retry uploading video")
    assert err.http_status == 409
    assert err.code == "INVALID_TRANSITION"


def test_transcription_failed_has_500_status_and_code() -> None:
    err = TranscriptionFailedError("whisper exploded")
    assert err.http_status == 500
    assert err.code == "TRANSCRIPTION_FAILED"


def test_worker_error_codes_enumerated() -> None:
    assert WorkerErrorCode.TRANSCRIPTION_FAILED == "TRANSCRIPTION_FAILED"
    assert WorkerErrorCode.AUDIO_DECODE_FAILED == "AUDIO_DECODE_FAILED"
    assert WorkerErrorCode.VRAM_UNAVAILABLE == "VRAM_UNAVAILABLE"
    assert WorkerErrorCode.TRANSCRIPTION_TIMEOUT == "TRANSCRIPTION_TIMEOUT"


def test_audio_decode_carries_worker_code() -> None:
    err = AudioDecodeFailedError("ffmpeg: invalid data")
    assert err.code == WorkerErrorCode.AUDIO_DECODE_FAILED.value


def test_transcription_timeout_carries_worker_code() -> None:
    err = TranscriptionTimeoutError("exceeded 4x duration")
    assert err.code == WorkerErrorCode.TRANSCRIPTION_TIMEOUT.value
