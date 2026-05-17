from datetime import UTC, datetime

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.features.transcription.repository import TranscriptRepository
from app.features.transcription.schemas import Segment, TranscriptDocument, Word


def _make_transcript(video_id: str | None = None) -> TranscriptDocument:
    return TranscriptDocument(
        id=str(ObjectId()),
        video_id=video_id or str(ObjectId()),
        language="en",
        language_probability=0.99,
        duration_sec=5.0,
        model_name="medium",
        model_version="float16",
        segments=[
            Segment(
                start=0.0,
                end=5.0,
                text="hello world",
                avg_logprob=-0.1,
                no_speech_prob=0.01,
                words=[
                    Word(word="hello", start=0.0, end=0.5, probability=0.97),
                    Word(word="world", start=0.6, end=1.1, probability=0.95),
                ],
            )
        ],
        created_at=datetime(2026, 5, 17, 10, 30, tzinfo=UTC),
    )


async def test_insert_persists_and_returns_document(test_db: AsyncIOMotorDatabase) -> None:
    repo = TranscriptRepository(test_db)
    transcript = _make_transcript()
    inserted = await repo.insert(transcript)
    assert inserted.id == transcript.id
    assert inserted.video_id == transcript.video_id


async def test_insert_stores_camelcase_keys_in_mongo(test_db: AsyncIOMotorDatabase) -> None:
    repo = TranscriptRepository(test_db)
    await repo.insert(_make_transcript())
    raw = await test_db["transcripts"].find_one({})
    assert raw is not None
    assert "videoId" in raw
    assert "languageProbability" in raw
    assert "durationSec" in raw
    assert "modelName" in raw
    assert raw["segments"][0]["avgLogprob"] == -0.1
    assert raw["segments"][0]["words"][0]["word"] == "hello"


async def test_get_by_video_id_returns_inserted(test_db: AsyncIOMotorDatabase) -> None:
    repo = TranscriptRepository(test_db)
    video_id = str(ObjectId())
    await repo.insert(_make_transcript(video_id=video_id))
    fetched = await repo.get_by_video_id(video_id)
    assert fetched is not None
    assert fetched.video_id == video_id
    assert fetched.segments[0].words[1].word == "world"


async def test_get_by_video_id_returns_none_when_missing(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = TranscriptRepository(test_db)
    fetched = await repo.get_by_video_id(str(ObjectId()))
    assert fetched is None


async def test_delete_by_video_id_returns_true_when_deleted(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = TranscriptRepository(test_db)
    video_id = str(ObjectId())
    await repo.insert(_make_transcript(video_id=video_id))
    deleted = await repo.delete_by_video_id(video_id)
    assert deleted is True
    assert await repo.get_by_video_id(video_id) is None


async def test_delete_by_video_id_returns_false_when_missing(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = TranscriptRepository(test_db)
    deleted = await repo.delete_by_video_id(str(ObjectId()))
    assert deleted is False
