"""Idempotent MongoDB initialization — creates collections and indexes.

Run: uv run python -m scripts.init_db
"""

import asyncio
import sys
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import CollectionInvalid

from app.core.config import get_settings
from app.core.db.client import close_client, get_db
from app.core.logging.setup import configure_logging, get_logger

COLLECTIONS = ("videos", "clips", "exports", "transcripts")

INDEXES: dict[str, list[tuple[str, list[tuple[str, int]], dict[str, Any]]]] = {
    "videos": [
        ("filename_idx", [("filename", ASCENDING)], {}),
        ("created_at_desc", [("createdAt", DESCENDING)], {}),
        ("status_idx", [("status", ASCENDING)], {}),
        ("content_hash_unique", [("contentHash", ASCENDING)], {"unique": True, "sparse": True}),
        (
            "status_started_idx",
            [("status", ASCENDING), ("transcriptionStartedAt", ASCENDING)],
            {},
        ),
    ],
    "clips": [
        ("video_id_idx", [("videoId", ASCENDING)], {}),
        ("virality_desc", [("viralityScore", DESCENDING)], {}),
        ("video_id_virality", [("videoId", ASCENDING), ("viralityScore", DESCENDING)], {}),
    ],
    "exports": [
        ("clip_id_idx", [("clipId", ASCENDING)], {}),
        ("created_at_desc", [("createdAt", DESCENDING)], {}),
    ],
    "transcripts": [
        ("video_id_unique", [("videoId", ASCENDING)], {"unique": True}),
    ],
}


async def apply_schema(db: AsyncIOMotorDatabase) -> None:
    log = get_logger("init_db")
    existing = set(await db.list_collection_names())
    for name in COLLECTIONS:
        if name in existing:
            log.info("collection_exists", name=name)
            continue
        try:
            await db.create_collection(name)
            log.info("collection_created", name=name)
        except CollectionInvalid as exc:
            log.warning("collection_create_skipped", name=name, reason=str(exc))

    for collection, specs in INDEXES.items():
        coll = db[collection]
        for index_name, keys, opts in specs:
            await coll.create_index(keys, name=index_name, **opts)
            log.info("index_ready", collection=collection, name=index_name)


async def init() -> int:
    configure_logging()
    log = get_logger("init_db")
    settings = get_settings()
    log.info("connecting", uri=settings.mongodb_uri, db=settings.mongodb_db)
    try:
        await apply_schema(get_db())
    except Exception as exc:
        log.error("init_failed", error=str(exc))
        await close_client()
        return 1
    await close_client()
    log.info("init_complete")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(init()))
