import os
from collections.abc import AsyncIterator

import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from scripts.init_db import apply_schema

SCHEMA_TEST_DB = "ai_clipper_schema_test"


@pytest_asyncio.fixture
async def schema_db() -> AsyncIterator[AsyncIOMotorDatabase]:
    uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(uri, tz_aware=True, serverSelectionTimeoutMS=2000)
    db = client[SCHEMA_TEST_DB]
    await client.drop_database(SCHEMA_TEST_DB)
    try:
        yield db
    finally:
        await client.drop_database(SCHEMA_TEST_DB)
        client.close()


async def test_apply_schema_creates_all_collections(
    schema_db: AsyncIOMotorDatabase,
) -> None:
    await apply_schema(schema_db)
    names = set(await schema_db.list_collection_names())
    assert {"videos", "clips", "exports"}.issubset(names)


async def test_apply_schema_creates_content_hash_unique_sparse_index(
    schema_db: AsyncIOMotorDatabase,
) -> None:
    await apply_schema(schema_db)
    indexes = await schema_db["videos"].index_information()
    assert "content_hash_unique" in indexes
    idx = indexes["content_hash_unique"]
    assert idx.get("unique") is True
    assert idx.get("sparse") is True
    assert idx["key"] == [("contentHash", 1)]


async def test_apply_schema_is_idempotent(schema_db: AsyncIOMotorDatabase) -> None:
    await apply_schema(schema_db)
    await apply_schema(schema_db)  # second run must not raise
    indexes = await schema_db["videos"].index_information()
    assert "content_hash_unique" in indexes


async def test_content_hash_uniqueness_enforced(
    schema_db: AsyncIOMotorDatabase,
) -> None:
    from pymongo.errors import DuplicateKeyError

    await apply_schema(schema_db)
    await schema_db["videos"].insert_one({"contentHash": "abc"})
    try:
        await schema_db["videos"].insert_one({"contentHash": "abc"})
    except DuplicateKeyError:
        return
    raise AssertionError("expected DuplicateKeyError on second insert")


async def test_content_hash_index_is_sparse_allowing_multiple_nulls(
    schema_db: AsyncIOMotorDatabase,
) -> None:
    await apply_schema(schema_db)
    await schema_db["videos"].insert_one({"filename": "a", "status": "uploading"})
    await schema_db["videos"].insert_one({"filename": "b", "status": "uploading"})
    count = await schema_db["videos"].count_documents({})
    assert count == 2
