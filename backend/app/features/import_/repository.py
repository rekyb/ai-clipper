from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo import DESCENDING

from app.features.import_.schemas import VideoDocument, VideoStatus

COLLECTION_NAME = "videos"


def _safe_object_id(raw: str) -> ObjectId | None:
    try:
        return ObjectId(raw)
    except (InvalidId, TypeError):
        return None


def _doc_from_raw(raw: Mapping[str, Any]) -> VideoDocument:
    data = dict(raw)
    data["_id"] = str(data["_id"])
    return VideoDocument.model_validate(data)


class VideoRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._collection: AsyncIOMotorCollection = db[COLLECTION_NAME]

    async def insert(self, doc: VideoDocument) -> VideoDocument:
        payload = doc.model_dump(by_alias=True, exclude={"id"})
        result = await self._collection.insert_one(payload)
        return doc.model_copy(update={"id": str(result.inserted_id)})

    async def get_by_id(self, video_id: str) -> VideoDocument | None:
        oid = _safe_object_id(video_id)
        if oid is None:
            return None
        raw = await self._collection.find_one({"_id": oid})
        return _doc_from_raw(raw) if raw is not None else None

    async def find_by_hash(self, content_hash: str) -> VideoDocument | None:
        raw = await self._collection.find_one({"contentHash": content_hash})
        return _doc_from_raw(raw) if raw is not None else None

    async def list_videos(self, *, status: VideoStatus | None) -> list[VideoDocument]:
        query: dict[str, Any] = {}
        if status is not None:
            query["status"] = status.value
        cursor = self._collection.find(query).sort("createdAt", DESCENDING)
        return [_doc_from_raw(raw) async for raw in cursor]

    async def update_status(
        self,
        video_id: str,
        *,
        status: VideoStatus,
        duration_sec: float | None = None,
        thumbnail_path: str | None = None,
        content_hash: str | None = None,
        container: str | None = None,
        file_size_bytes: int | None = None,
        storage_path: str | None = None,
        title: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> VideoDocument | None:
        oid = _safe_object_id(video_id)
        if oid is None:
            return None
        update: dict[str, Any] = {
            "status": status.value,
            "updatedAt": datetime.now(UTC),
        }
        if duration_sec is not None:
            update["durationSec"] = duration_sec
        if thumbnail_path is not None:
            update["thumbnailPath"] = thumbnail_path
        if content_hash is not None:
            update["contentHash"] = content_hash
        if container is not None:
            update["container"] = container
        if file_size_bytes is not None:
            update["fileSizeBytes"] = file_size_bytes
        if storage_path is not None:
            update["storagePath"] = storage_path
        if title is not None:
            update["title"] = title
        if error_code is not None:
            update["errorCode"] = error_code
        if error_message is not None:
            update["errorMessage"] = error_message

        raw = await self._collection.find_one_and_update(
            {"_id": oid},
            {"$set": update},
            return_document=True,
        )
        return _doc_from_raw(raw) if raw is not None else None

    async def delete(self, video_id: str) -> bool:
        oid = _safe_object_id(video_id)
        if oid is None:
            return False
        result = await self._collection.delete_one({"_id": oid})
        return result.deleted_count > 0
