from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.core.schemas.video_status import VideoStatus
from app.features.import_.schemas import (
    UrlImportRequest,
    VideoDocument,
    VideoListResponse,
    VideoSource,
)


def test_video_status_enum_values_are_lowercase_strings() -> None:
    assert VideoStatus.UPLOADING.value == "uploading"
    assert VideoStatus.IMPORTED.value == "imported"
    assert VideoStatus.FAILED.value == "failed"


def test_video_status_round_trips_through_string() -> None:
    assert VideoStatus("imported") is VideoStatus.IMPORTED


def test_video_source_enum_values_are_lowercase_strings() -> None:
    assert VideoSource.UPLOAD.value == "upload"
    assert VideoSource.YOUTUBE.value == "youtube"


def _sample_video_document() -> VideoDocument:
    now = datetime(2026, 5, 17, 10, 30, tzinfo=UTC)
    return VideoDocument(
        id="65f1a2b3c4d5e6f7a8b9c0d1",
        filename="my-podcast.mp4",
        title="My Podcast Episode 12",
        source=VideoSource.UPLOAD,
        source_url=None,
        storage_path="/media/originals/65f1.../my-podcast.mp4",
        thumbnail_path="/media/thumbnails/65f1a2b3c4d5e6f7a8b9c0d1.jpg",
        duration_sec=1834.5,
        file_size_bytes=524_288_000,
        container="mp4",
        content_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        status=VideoStatus.IMPORTED,
        error_code=None,
        error_message=None,
        created_at=now,
        updated_at=now,
    )


def test_video_document_serializes_to_dict_and_back() -> None:
    original = _sample_video_document()
    dumped = original.model_dump()
    reloaded = VideoDocument.model_validate(dumped)
    assert reloaded == original


def test_video_document_dumps_camelcase_keys_for_mongo() -> None:
    doc = _sample_video_document()
    mongo = doc.model_dump(by_alias=True)
    assert "sourceUrl" in mongo
    assert "storagePath" in mongo
    assert "thumbnailPath" in mongo
    assert "durationSec" in mongo
    assert "fileSizeBytes" in mongo
    assert "contentHash" in mongo
    assert "createdAt" in mongo
    assert "id" in mongo  # API-facing serialization (Mongo's _id is added by the repo)


def test_video_document_validates_from_mongo_shape() -> None:
    now = datetime(2026, 5, 17, 10, 30, tzinfo=UTC)
    raw = {
        "_id": "65f1a2b3c4d5e6f7a8b9c0d1",
        "filename": "foo.mp4",
        "title": "Foo",
        "source": "upload",
        "sourceUrl": None,
        "storagePath": "/path/foo.mp4",
        "thumbnailPath": None,
        "durationSec": 100.0,
        "fileSizeBytes": 1000,
        "container": "mp4",
        "contentHash": "abc",
        "status": "imported",
        "errorCode": None,
        "errorMessage": None,
        "createdAt": now,
        "updatedAt": now,
    }
    doc = VideoDocument.model_validate(raw)
    assert doc.id == "65f1a2b3c4d5e6f7a8b9c0d1"
    assert doc.thumbnail_path is None
    assert doc.content_hash == "abc"


def test_video_document_allows_nullable_metadata_while_uploading() -> None:
    now = datetime(2026, 5, 17, 10, 30, tzinfo=UTC)
    doc = VideoDocument(
        id="65f1a2b3c4d5e6f7a8b9c0d2",
        filename="placeholder",
        title="https://youtu.be/abc123",
        source=VideoSource.YOUTUBE,
        source_url="https://youtu.be/abc123",
        storage_path="",
        thumbnail_path=None,
        duration_sec=None,
        file_size_bytes=0,
        container=None,
        content_hash=None,
        status=VideoStatus.UPLOADING,
        error_code=None,
        error_message=None,
        created_at=now,
        updated_at=now,
    )
    assert doc.status is VideoStatus.UPLOADING
    assert doc.thumbnail_path is None
    assert doc.duration_sec is None
    assert doc.content_hash is None


def test_url_import_request_accepts_youtube_url() -> None:
    request = UrlImportRequest(url="https://youtu.be/dQw4w9WgXcQ")
    assert str(request.url).startswith("https://youtu.be/")


def test_url_import_request_rejects_non_url_string() -> None:
    with pytest.raises(ValidationError):
        UrlImportRequest(url="not a url")


def test_video_list_response_accepts_empty_list() -> None:
    response = VideoListResponse(videos=[])
    assert response.videos == []


def test_video_list_response_accepts_populated_list() -> None:
    response = VideoListResponse(videos=[_sample_video_document()])
    assert len(response.videos) == 1
    assert response.videos[0].status is VideoStatus.IMPORTED
