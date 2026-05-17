class ImportDomainError(Exception):
    code: str = "INVALID_INPUT"
    http_status: int = 400


class InvalidInputError(ImportDomainError):
    pass


class VideoTooLargeError(ImportDomainError):
    code = "FILE_TOO_LARGE"
    http_status = 413


class UnsupportedFormatError(ImportDomainError):
    code = "UNSUPPORTED_FORMAT"
    http_status = 422


class DurationExceededError(ImportDomainError):
    code = "DURATION_EXCEEDED"
    http_status = 422


class DuplicateVideoError(ImportDomainError):
    code = "DUPLICATE_VIDEO"
    http_status = 409

    def __init__(self, message: str, *, existing_title: str | None = None) -> None:
        super().__init__(message)
        self.existing_title = existing_title


class InvalidUrlError(ImportDomainError):
    code = "INVALID_URL"
    http_status = 400


class UnsupportedHostError(ImportDomainError):
    code = "UNSUPPORTED_HOST"
    http_status = 400


class VideoNotFoundError(ImportDomainError):
    code = "NOT_FOUND"
    http_status = 404


class StorageError(ImportDomainError):
    code = "STORAGE_ERROR"
    http_status = 500


ASYNC_ERROR_CODES: frozenset[str] = frozenset(
    {
        "DOWNLOAD_FAILED",
        "VIDEO_PRIVATE",
        "VIDEO_REMOVED",
        "VIDEO_AGE_GATED",
        "VIDEO_REGION_BLOCKED",
    }
)
