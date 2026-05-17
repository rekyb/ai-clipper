from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

from app.core.schemas.video_status import VideoStatus
from app.features.import_.schemas import VideoDocument

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
        if doc.id:
            payload["_id"] = ObjectId(doc.id)
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

    async def list_videos(
        self,
        *,
        status: VideoStatus | None = None,
        statuses: list[VideoStatus] | None = None,
    ) -> list[VideoDocument]:
        query: dict[str, Any] = {}
        if statuses is not None:
            query["status"] = {"$in": [s.value for s in statuses]}
        elif status is not None:
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

    async def transition_status(
        self,
        video_id: str,
        *,
        from_status: VideoStatus | set[VideoStatus],
        to_status: VideoStatus,
        set_fields: dict[str, Any] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        clear_error: bool = False,
    ) -> VideoDocument | None:
        oid = _safe_object_id(video_id)
        if oid is None:
            return None
        if isinstance(from_status, VideoStatus):
            from_filter: dict[str, Any] = {"status": from_status.value}
        else:
            from_filter = {"status": {"$in": [s.value for s in from_status]}}
        update_set: dict[str, Any] = {
            "status": to_status.value,
            "updatedAt": datetime.now(UTC),
        }
        if set_fields:
            update_set.update(set_fields)
        if error_code is not None:
            update_set["errorCode"] = error_code
        if error_message is not None:
            update_set["errorMessage"] = error_message
        update_doc: dict[str, Any] = {"$set": update_set}
        if clear_error:
            update_doc["$unset"] = {"errorCode": "", "errorMessage": ""}
        raw = await self._collection.find_one_and_update(
            {"_id": oid, **from_filter},
            update_doc,
            return_document=True,
        )
        return _doc_from_raw(raw) if raw is not None else None

    async def claim_next_queued(self) -> VideoDocument | None:
        now = datetime.now(UTC)
        raw = await self._collection.find_one_and_update(
            {"status": VideoStatus.QUEUED.value},
            {
                "$set": {
                    "status": VideoStatus.TRANSCRIBING.value,
                    "transcriptionStartedAt": now,
                    "updatedAt": now,
                }
            },
            sort=[("createdAt", ASCENDING)],
            return_document=True,
        )
        return _doc_from_raw(raw) if raw is not None else None

    async def update_progress(self, video_id: str, *, percent: int) -> None:
        oid = _safe_object_id(video_id)
        if oid is None:
            return
        await self._collection.update_one(
            {"_id": oid},
            {"$set": {"lastProgressPercent": percent}},
        )

    async def sweep_stale_transcribing(self) -> list[str]:
        now = datetime.now(UTC)
        affected: list[str] = []
        cursor = self._collection.find({"status": VideoStatus.TRANSCRIBING.value}, {"_id": 1})
        async for raw in cursor:
            affected.append(str(raw["_id"]))
        if not affected:
            return []
        await self._collection.update_many(
            {"_id": {"$in": [ObjectId(vid) for vid in affected]}},
            {
                "$set": {
                    "status": VideoStatus.QUEUED.value,
                    "restartedAt": now,
                    "updatedAt": now,
                }
            },
        )
        return affected

    async def back_fill_imported(self) -> list[str]:
        now = datetime.now(UTC)
        affected: list[str] = []
        cursor = self._collection.find({"status": VideoStatus.IMPORTED.value}, {"_id": 1})
        async for raw in cursor:
            affected.append(str(raw["_id"]))
        if not affected:
            return []
        await self._collection.update_many(
            {"_id": {"$in": [ObjectId(vid) for vid in affected]}},
            {
                "$set": {
                    "status": VideoStatus.QUEUED.value,
                    "updatedAt": now,
                }
            },
        )
        return affected

    async def count_queued_before(self, video_id: str) -> int:
        oid = _safe_object_id(video_id)
        if oid is None:
            return 0
        target = await self._collection.find_one({"_id": oid}, {"createdAt": 1})
        if target is None:
            return 0
        return await self._collection.count_documents(
            {
                "status": VideoStatus.QUEUED.value,
                "createdAt": {"$lt": target["createdAt"]},
            }
        )
