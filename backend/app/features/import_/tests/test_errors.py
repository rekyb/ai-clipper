import pytest

from app.features.import_.errors import (
    DuplicateVideoError,
    DurationExceededError,
    ImportDomainError,
    InvalidInputError,
    InvalidUrlError,
    StorageError,
    UnsupportedFormatError,
    UnsupportedHostError,
    VideoNotFoundError,
    VideoTooLargeError,
)


@pytest.mark.parametrize(
    ("exc_class", "expected_code", "expected_status"),
    [
        (InvalidInputError, "INVALID_INPUT", 400),
        (VideoTooLargeError, "FILE_TOO_LARGE", 413),
        (UnsupportedFormatError, "UNSUPPORTED_FORMAT", 422),
        (DurationExceededError, "DURATION_EXCEEDED", 422),
        (DuplicateVideoError, "DUPLICATE_VIDEO", 409),
        (InvalidUrlError, "INVALID_URL", 400),
        (UnsupportedHostError, "UNSUPPORTED_HOST", 400),
        (VideoNotFoundError, "NOT_FOUND", 404),
        (StorageError, "STORAGE_ERROR", 500),
    ],
)
def test_each_domain_error_has_code_and_http_status(
    exc_class: type[ImportDomainError],
    expected_code: str,
    expected_status: int,
) -> None:
    exc = exc_class("something happened")
    assert exc.code == expected_code
    assert exc.http_status == expected_status


def test_all_domain_errors_inherit_from_base() -> None:
    for cls in (
        InvalidInputError,
        VideoTooLargeError,
        UnsupportedFormatError,
        DurationExceededError,
        DuplicateVideoError,
        InvalidUrlError,
        UnsupportedHostError,
        VideoNotFoundError,
        StorageError,
    ):
        assert issubclass(cls, ImportDomainError)


def test_base_domain_error_is_an_exception() -> None:
    assert issubclass(ImportDomainError, Exception)


def test_domain_error_carries_message() -> None:
    exc = DuplicateVideoError("video 'foo.mp4' already imported")
    assert str(exc) == "video 'foo.mp4' already imported"


def test_duplicate_video_error_can_carry_existing_title() -> None:
    exc = DuplicateVideoError("already exists", existing_title="My Podcast")
    assert exc.existing_title == "My Podcast"
