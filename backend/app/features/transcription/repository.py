from collections.abc import Mapping
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase

from app.features.transcription.schemas import TranscriptDocument

COLLECTION_NAME = "transcripts"


def _safe_object_id(raw: str) -> ObjectId | None:
    try:
        return ObjectId(raw)
    except (InvalidId, TypeError):
        return None


def _doc_from_raw(raw: Mapping[str, Any]) -> TranscriptDocument:
    data = dict(raw)
    data["_id"] = str(data["_id"])
    return TranscriptDocument.model_validate(data)


class TranscriptRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._collection: AsyncIOMotorCollection = db[COLLECTION_NAME]

    async def insert(self, doc: TranscriptDocument) -> TranscriptDocument:
        payload = doc.model_dump(by_alias=True, exclude={"id"})
        if doc.id:
            payload["_id"] = ObjectId(doc.id)
        result = await self._collection.insert_one(payload)
        return doc.model_copy(update={"id": str(result.inserted_id)})

    async def get_by_video_id(self, video_id: str) -> TranscriptDocument | None:
        raw = await self._collection.find_one({"videoId": video_id})
        return _doc_from_raw(raw) if raw is not None else None

    async def delete_by_video_id(self, video_id: str) -> bool:
        result = await self._collection.delete_one({"videoId": video_id})
        return result.deleted_count > 0
