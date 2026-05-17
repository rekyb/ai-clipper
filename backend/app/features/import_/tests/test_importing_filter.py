from datetime import UTC, datetime

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.schemas.video_status import VideoStatus
from app.features.import_.repository import VideoRepository
from app.features.import_.schemas import VideoDocument, VideoSource


def _make_doc(*, status: VideoStatus, filename: str = "x.mp4") -> VideoDocument:
    now = datetime.now(UTC)
    return VideoDocument(
        id=str(ObjectId()),
        filename=filename,
        title=filename,
        source=VideoSource.UPLOAD,
        source_url=None,
        storage_path=f"/x/{filename}",
        thumbnail_path=None,
        duration_sec=10.0,
        file_size_bytes=1,
        container="mp4",
        content_hash=f"hash-{filename}",
        status=status,
        error_code=None,
        error_message=None,
        created_at=now,
        updated_at=now,
    )


async def test_list_videos_accepts_status_list(test_db: AsyncIOMotorDatabase) -> None:
    repo = VideoRepository(test_db)
    await repo.insert(_make_doc(status=VideoStatus.UPLOADING, filename="u.mp4"))
    await repo.insert(_make_doc(status=VideoStatus.IMPORTED, filename="i.mp4"))
    await repo.insert(_make_doc(status=VideoStatus.READY, filename="r.mp4"))

    importing = await repo.list_videos(statuses=[VideoStatus.UPLOADING, VideoStatus.IMPORTED])
    filenames = {d.filename for d in importing}
    assert filenames == {"u.mp4", "i.mp4"}


async def test_list_videos_statuses_takes_precedence_over_status(
    test_db: AsyncIOMotorDatabase,
) -> None:
    repo = VideoRepository(test_db)
    await repo.insert(_make_doc(status=VideoStatus.UPLOADING))
    await repo.insert(_make_doc(status=VideoStatus.IMPORTED))

    docs = await repo.list_videos(
        status=VideoStatus.READY,
        statuses=[VideoStatus.UPLOADING, VideoStatus.IMPORTED],
    )
    assert len(docs) == 2
