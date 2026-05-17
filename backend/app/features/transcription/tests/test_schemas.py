from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.core.schemas.video_status import VideoStatus
from app.features.transcription.schemas import (
    ProgressEvent,
    RetryResponse,
    Segment,
    TranscriptDocument,
    Word,
)


def test_video_status_includes_new_transcription_states() -> None:
    assert VideoStatus.QUEUED.value == "queued"
    assert VideoStatus.TRANSCRIBING.value == "transcribing"
    assert VideoStatus.READY.value == "ready"


def test_video_status_retains_original_states() -> None:
    assert VideoStatus.UPLOADING.value == "uploading"
    assert VideoStatus.IMPORTED.value == "imported"
    assert VideoStatus.FAILED.value == "failed"


def _sample_word(offset: float = 0.0) -> Word:
    return Word(word="hello", start=offset, end=offset + 0.5, probability=0.97)


def _sample_segment() -> Segment:
    return Segment(
        start=0.0,
        end=2.5,
        text="hello world",
        avg_logprob=-0.12,
        no_speech_prob=0.01,
        words=[_sample_word(0.0), _sample_word(0.6)],
    )


def _sample_transcript() -> TranscriptDocument:
    return TranscriptDocument(
        id="65f1a2b3c4d5e6f7a8b9c0d1",
        video_id="65f1a2b3c4d5e6f7a8b9c0d2",
        language="en",
        language_probability=0.99,
        duration_sec=2.5,
        model_name="medium",
        model_version="float16",
        segments=[_sample_segment()],
        created_at=datetime(2026, 5, 17, 10, 30, tzinfo=UTC),
    )


def test_word_serializes_round_trip() -> None:
    w = _sample_word(1.0)
    dumped = w.model_dump()
    reloaded = Word.model_validate(dumped)
    assert reloaded == w


def test_segment_dumps_camelcase_keys_for_mongo() -> None:
    seg = _sample_segment()
    mongo = seg.model_dump(by_alias=True)
    assert "avgLogprob" in mongo
    assert "noSpeechProb" in mongo
    assert "words" in mongo


def test_transcript_document_dumps_camelcase_keys() -> None:
    doc = _sample_transcript()
    mongo = doc.model_dump(by_alias=True)
    assert "videoId" in mongo
    assert "languageProbability" in mongo
    assert "durationSec" in mongo
    assert "modelName" in mongo
    assert "modelVersion" in mongo
    assert "createdAt" in mongo
    assert "id" in mongo


def test_transcript_document_validates_from_mongo_shape() -> None:
    raw = {
        "_id": "65f1a2b3c4d5e6f7a8b9c0d1",
        "videoId": "65f1a2b3c4d5e6f7a8b9c0d2",
        "language": "en",
        "languageProbability": 0.99,
        "durationSec": 2.5,
        "modelName": "medium",
        "modelVersion": "float16",
        "segments": [
            {
                "start": 0.0,
                "end": 2.5,
                "text": "hello world",
                "avgLogprob": -0.12,
                "noSpeechProb": 0.01,
                "words": [
                    {"word": "hello", "start": 0.0, "end": 0.5, "probability": 0.97},
                ],
            }
        ],
        "createdAt": datetime(2026, 5, 17, 10, 30, tzinfo=UTC),
    }
    doc = TranscriptDocument.model_validate(raw)
    assert doc.id == "65f1a2b3c4d5e6f7a8b9c0d1"
    assert doc.video_id == "65f1a2b3c4d5e6f7a8b9c0d2"
    assert doc.segments[0].words[0].word == "hello"


def test_progress_event_snapshot_includes_all_fields() -> None:
    event = ProgressEvent(
        type="snapshot",
        video_id="vid-1",
        status=VideoStatus.TRANSCRIBING,
        percent=47,
        stage="transcription",
        segments_done=10,
        segments_total=20,
        elapsed_sec=12.5,
        eta_sec=15.0,
    )
    payload = event.model_dump(by_alias=True)
    assert payload["type"] == "snapshot"
    assert payload["videoId"] == "vid-1"
    assert payload["status"] == "transcribing"
    assert payload["segmentsDone"] == 10
    assert payload["elapsedSec"] == 12.5
    assert payload["etaSec"] == 15.0


def test_progress_event_for_queued_includes_position() -> None:
    event = ProgressEvent(
        type="snapshot",
        video_id="vid-2",
        status=VideoStatus.QUEUED,
        percent=0,
        stage="transcription",
        elapsed_sec=0.0,
        queue_position=3,
    )
    payload = event.model_dump(by_alias=True)
    assert payload["queuePosition"] == 3


def test_progress_event_for_error_includes_error_fields() -> None:
    event = ProgressEvent(
        type="error",
        video_id="vid-3",
        status=VideoStatus.FAILED,
        percent=0,
        stage="transcription",
        elapsed_sec=5.0,
        error_code="VRAM_UNAVAILABLE",
        error_message="Requested 2.3 GB but only 1.5 GB available",
    )
    payload = event.model_dump(by_alias=True)
    assert payload["errorCode"] == "VRAM_UNAVAILABLE"
    assert "1.5 GB" in payload["errorMessage"]


def test_progress_event_rejects_unknown_type() -> None:
    with pytest.raises(ValidationError):
        ProgressEvent.model_validate(
            {
                "type": "bogus",
                "videoId": "vid-1",
                "status": "queued",
                "percent": 0,
                "stage": "transcription",
                "elapsedSec": 0.0,
            }
        )


def test_retry_response_serializes_with_camelcase_via_by_alias() -> None:
    r = RetryResponse(id="vid-1", status=VideoStatus.QUEUED)
    assert r.model_dump(by_alias=True) == {"id": "vid-1", "status": "queued"}
