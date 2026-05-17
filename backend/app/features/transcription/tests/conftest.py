import os
from collections.abc import AsyncIterator

import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

TEST_DB_NAME = "ai_clipper_transcription_test"


@pytest_asyncio.fixture
async def test_db() -> AsyncIterator[AsyncIOMotorDatabase]:
    uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(uri, tz_aware=True, serverSelectionTimeoutMS=2000)
    db = client[TEST_DB_NAME]
    await client.drop_database(TEST_DB_NAME)
    try:
        yield db
    finally:
        await client.drop_database(TEST_DB_NAME)
        client.close()
