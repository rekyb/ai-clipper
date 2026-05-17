# Technical Design Document: Video Import Foundation

**Feature:** Video Import (Phase 2, Chunk 2A)
**Version:** 1.1
**Date:** 2026-05-17
**Author:** Tech Lead
**Implements:** `video-import-prd.md` (v1.1, approved)
**Design System:** Conforms to `DESIGN.md` (Vivid Velocity). All frontend work consumes Vivid Velocity tokens — no new visual style introduced. Phase 1's placeholder theme is reconciled to DESIGN.md as part of this chunk.

---

## 1. Architecture Overview

```
┌─────────────────────────────┐         ┌────────────────────────────────────┐
│  Browser (Next.js 16)       │         │  FastAPI Backend                   │
│  features/import/           │  HTTP   │  features/import/                  │
│  ┌───────────────────────┐  │ ──────▶ │  ┌──────────────────────────────┐  │
│  │ UploadDropzone        │  │ POST    │  │ routes.py                    │  │
│  │ UrlImportForm         │  │         │  │   /api/videos/upload         │  │
│  │ VideoLibrary (SWR)    │  │ ◀────── │  │   /api/videos/download-url   │  │
│  │ VideoCard             │  │         │  │   /api/videos (list)         │  │
│  │ DeleteConfirmDialog   │  │ DELETE  │  │   /api/videos/{id}           │  │
│  └───────────────────────┘  │         │  └──────────────────────────────┘  │
└─────────────────────────────┘         │  ┌──────────────────────────────┐  │
                                        │  │ service.py                   │  │
                                        │  │  import_uploaded_file        │  │
                                        │  │  import_from_url             │  │
                                        │  │  list_videos / delete_video  │  │
                                        │  └──────────────────────────────┘  │
                                        │     │            │           │     │
                                        │     ▼            ▼           ▼     │
                                        │ ┌─────────┐ ┌────────┐ ┌──────────┐│
                                        │ │ media.py│ │youtube │ │repository││
                                        │ │ ffprobe │ │ .py    │ │ .py      ││
                                        │ │ thumb   │ │ yt-dlp │ │ Motor    ││
                                        │ │ hash    │ │        │ │          ││
                                        │ └─────────┘ └────────┘ └──────────┘│
                                        │                            │       │
                                        └────────────────────────────┼───────┘
                                                                     ▼
                                                              ┌─────────────┐
                                                              │  MongoDB    │
                                                              │  videos     │
                                                              └─────────────┘
                                                              ┌─────────────┐
                                                              │  Filesystem │
                                                              │  media/     │
                                                              │  originals/ │
                                                              │  thumbnails/│
                                                              └─────────────┘
```

**Pipeline (upload):** browser → multipart stream → backend writes to `media/originals/.tmp/{uuid}` while computing SHA-256 → validate size cap → ffprobe (duration + container + has-video-stream) → reject or move to `media/originals/{video_id}/{filename}` → extract thumbnail at 10% mark → persist record (`status=imported`).

**Pipeline (URL):** browser → POST JSON `{ url }` → backend validates host → creates DB record (`status=uploading`) → returns `video_id` immediately → background task runs yt-dlp to temp → same hash/probe/thumbnail pipeline → updates record to `imported` or `failed`.

**Pipeline (list):** SWR poll → backend reads `videos` collection sorted `createdAt desc`, optional `status` filter → returns array → frontend renders cards. SWR re-polls every 3s only while at least one record has `status=uploading`.

**Pipeline (delete):** browser → confirm dialog → DELETE → backend removes file + thumbnail + record → SWR revalidates.

---

## 2. Backend Design

### 2.1 Feature Folder Layout

```
backend/app/features/import/
├── __init__.py
├── routes.py              # FastAPI APIRouter, HTTP boundary
├── service.py             # Business logic, raises domain exceptions
├── repository.py          # Motor data access, returns Pydantic models
├── schemas.py             # Pydantic request/response/document models
├── errors.py              # Domain exception types + error code enum
├── media.py               # ffprobe wrapper, thumbnail extraction, hashing
├── youtube.py             # yt-dlp wrapper (sync, called via thread pool)
├── tasks.py               # Background task runner for URL imports
└── tests/
    ├── __init__.py
    ├── conftest.py        # fixture videos (5s mp4, 3s mkv, audio-only mp4)
    ├── test_routes.py     # API integration tests against test DB
    ├── test_service.py    # Service-layer unit tests (mocked I/O)
    ├── test_media.py      # ffprobe + thumbnail tests against fixtures
    └── test_repository.py # Motor CRUD against test DB
```

Wired into `app/main.py`:

```python
from app.features.import_ import routes as import_routes  # 'import' is reserved
app.include_router(import_routes.router, prefix="/api")
```

Folder named `import_` on the filesystem because `import` is a Python keyword. Module-level alias is fine.

### 2.2 Data Model

**MongoDB document (`videos` collection):**

| Field            | Type     | Notes                                                              |
|------------------|----------|--------------------------------------------------------------------|
| `_id`            | ObjectId | Mongo primary key. Exposed as `id` (str) in API.                   |
| `filename`       | string   | Sanitized filename, no path. Indexed (Phase 1).                   |
| `title`          | string   | Display title. For uploads = filename stem. For YouTube = video title from yt-dlp metadata. |
| `source`         | enum     | `"upload"` \| `"youtube"`                                           |
| `sourceUrl`      | string?  | Original URL for YouTube imports. Null for uploads.                |
| `storagePath`    | string   | Absolute path to source file under `media/originals/`.             |
| `thumbnailPath`  | string?  | Absolute path under `media/thumbnails/`. Null while `uploading`.   |
| `durationSec`    | float?   | Null while `uploading`.                                            |
| `fileSizeBytes`  | int      | Bytes on disk. For `uploading` records, may be 0 until complete.   |
| `container`      | string?  | `"mp4"` / `"mkv"` etc. Null while `uploading`.                     |
| `contentHash`    | string?  | SHA-256 hex. Null while `uploading`. Unique index when present.    |
| `status`         | enum     | `"uploading"` \| `"imported"` \| `"failed"`. Indexed (Phase 1).    |
| `errorCode`      | string?  | Set when `status=failed`. See §2.6 catalog.                        |
| `errorMessage`   | string?  | Human-readable failure detail.                                     |
| `createdAt`      | datetime | UTC. Indexed desc (Phase 1).                                       |
| `updatedAt`      | datetime | UTC. Bumped on every write.                                        |

**Schema delta from Phase 1:** The `videos` collection exists with three indexes (`filename_idx`, `created_at_desc`, `status_idx`). This chunk adds:
- One sparse unique index on `contentHash` (sparse = ignores docs where field is null/absent, so `uploading` records do not conflict).

Migration: add the index in `scripts/init_db.py`'s `INDEXES["videos"]` list. The script is idempotent, so re-running it during deploy is safe.

**Pydantic models (`schemas.py`):**

```python
class VideoStatus(str, Enum):
    UPLOADING = "uploading"
    IMPORTED = "imported"
    FAILED = "failed"

class VideoSource(str, Enum):
    UPLOAD = "upload"
    YOUTUBE = "youtube"

class VideoDocument(BaseModel):
    id: str                           # serialized from ObjectId
    filename: str
    title: str
    source: VideoSource
    source_url: str | None
    storage_path: str
    thumbnail_url: str | None         # API-facing: HTTP path, not disk path
    duration_sec: float | None
    file_size_bytes: int
    container: str | None
    status: VideoStatus
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class UrlImportRequest(BaseModel):
    url: HttpUrl

class VideoListResponse(BaseModel):
    videos: list[VideoDocument]
```

The API exposes `thumbnail_url` (e.g., `/media/thumbnails/abc.jpg`) rather than `thumbnail_path`. The disk path stays internal. A `StaticFiles` mount at `/media/thumbnails/` serves these files.

### 2.3 API Contracts

All responses use the existing envelope (`{ data, error, meta? }`) from `app/main.py`'s `/health` endpoint. The contract is defined in `frontend/src/lib/api.ts`.

#### `POST /api/videos/upload`
- **Content-Type:** `multipart/form-data`, single field `file`.
- **Response 201:** `{ data: VideoDocument, error: null }`
- **Errors:**
  - 400 `INVALID_INPUT` — no file in form
  - 413 `FILE_TOO_LARGE` — exceeds 5GB cap (checked via Content-Length and streaming watchdog)
  - 422 `UNSUPPORTED_FORMAT` — container not in allowlist or no video stream
  - 422 `DURATION_EXCEEDED` — duration > 14400s
  - 409 `DUPLICATE_VIDEO` — hash already present; error message includes existing video title
  - 500 `STORAGE_ERROR` — disk write or move failure

#### `POST /api/videos/download-url`
- **Body:** `{ "url": "https://youtu.be/..." }`
- **Response 202:** `{ data: VideoDocument, error: null }` — record with `status=uploading`. Client polls for completion.
- **Errors (synchronous, before background task):**
  - 400 `INVALID_URL` — yt-dlp cannot parse
  - 400 `UNSUPPORTED_HOST` — host not in `["youtube.com", "youtu.be", "www.youtube.com", "m.youtube.com"]`
- **Errors (async, persisted on the record):**
  - `DOWNLOAD_FAILED` — generic network or yt-dlp failure
  - `VIDEO_PRIVATE` — yt-dlp reports private
  - `VIDEO_REMOVED` — yt-dlp reports unavailable
  - `VIDEO_AGE_GATED` — yt-dlp reports age restriction
  - `VIDEO_REGION_BLOCKED` — yt-dlp reports geo-restriction
  - Plus the same post-download codes as upload (`UNSUPPORTED_FORMAT`, `DURATION_EXCEEDED`, `DUPLICATE_VIDEO`).

#### `GET /api/videos`
- **Query params:** `status` (optional, one of the status enum values).
- **Response 200:** `{ data: { videos: VideoDocument[] }, error: null }`
- Sorted by `createdAt desc`. No pagination in 2A (50-record budget per PRD performance KPI; pagination is a Phase 6 concern).

#### `DELETE /api/videos/{id}`
- **Response 200:** `{ data: { id: string, deleted: true }, error: null }`
- **Errors:**
  - 404 `NOT_FOUND` — id does not exist or already deleted
  - 400 `INVALID_INPUT` — id is not a valid ObjectId
  - 500 `STORAGE_ERROR` — DB delete succeeded but file delete failed (the record is gone; the orphaned file is logged for manual cleanup — record removal is the source of truth)

### 2.4 Service Layer Responsibilities

`service.py` exposes four functions. Each is async. None raises `HTTPException` — they raise domain exceptions from `errors.py`, and `routes.py` translates.

```python
async def import_uploaded_file(file: UploadFile) -> VideoDocument: ...
async def import_from_url(url: str) -> VideoDocument: ...
async def list_videos(status: VideoStatus | None) -> list[VideoDocument]: ...
async def delete_video(video_id: str) -> None: ...
```

**`import_uploaded_file`:**
1. Generate `video_id` (ObjectId) and temp path `media/originals/.tmp/{video_id}`.
2. Stream-write file to temp path in 1MB chunks. Update SHA-256 per chunk. Track bytes written; abort with `VideoTooLargeError` if > 5GB.
3. Run `media.probe(temp_path)` — returns `(duration_sec, container, has_video)`. If container not in allowlist or no video stream → `UnsupportedFormatError`. If `duration_sec > 14400` → `DurationExceededError`.
4. Hash check: `repository.find_by_hash(hash)` → if exists, delete temp file, raise `DuplicateVideoError(existing.title)`.
5. Move temp file to `media/originals/{video_id}/{sanitized_filename}`. Sanitize filename: strip path components, replace control chars and `/\:*?"<>|` with `_`, truncate to 200 chars.
6. Extract thumbnail: `media.extract_thumbnail(final_path, video_id)` → returns `media/thumbnails/{video_id}.jpg`.
7. Insert record with `status=imported`. Return Pydantic model.
8. On any exception after step 1, attempt cleanup (delete temp + final + thumbnail). Cleanup is best-effort and logged.

**`import_from_url`:**
1. Validate URL host against allowlist → `UnsupportedHostError` if mismatch.
2. Insert placeholder record: `status=uploading`, `source=youtube`, `source_url=url`, `title=url` (will be overwritten), `storage_path=""`, `file_size_bytes=0`.
3. Return Pydantic model immediately (response 202).
4. Schedule background task `tasks.download_youtube(video_id, url)`.

**`tasks.download_youtube`:**
1. Run yt-dlp in `asyncio.to_thread(...)` → writes to `media/originals/.tmp/{video_id}` and returns `{title, filename, ...}`.
2. From this point, same as upload steps 3–7, with the placeholder record updated rather than inserted.
3. On any failure, update record to `status=failed` with appropriate `error_code` and `error_message`. Delete temp file.

**`list_videos`:** Pass-through to `repository.list_videos(status)`.

**`delete_video`:**
1. `repository.get_by_id(video_id)` → `VideoNotFoundError` if missing.
2. `repository.delete(video_id)` first (DB is source of truth).
3. Best-effort delete of `storage_path` and `thumbnail_path`. Log failures, do not raise.

### 2.5 Media Operations (`media.py`)

Three pure async helpers. All shell out to ffmpeg/ffprobe via `asyncio.create_subprocess_exec` — no `ffmpeg-python` wrapper (its API is sync and we want native asyncio).

```python
async def probe(path: Path) -> ProbeResult:
    """Run ffprobe, return duration_sec, container, has_video_stream."""

async def extract_thumbnail(source: Path, video_id: str) -> Path:
    """ffmpeg -ss {duration*0.1} -i {source} -vframes 1 -vf scale=320:-1 -q:v 5 thumbnails/{video_id}.jpg"""

async def hash_stream(reader: AsyncIterator[bytes]) -> tuple[str, int]:
    """Consume reader, return (sha256_hex, total_bytes). Used during streaming upload."""
```

Why subprocess over a library: ffmpeg-python is a thin string builder; subprocess gives us proper async, clear errors, no extra dep, and identical behavior on Windows.

**Probe result:** Parse `ffprobe -v error -print_format json -show_format -show_streams`. Container comes from `format.format_name` (mapped: `mov,mp4,m4a,3gp,3g2,mj2` → `mp4`; `matroska,webm` → distinguish by extension; etc.). Has-video is `any(stream.codec_type == "video" for stream in streams)`.

**Allowlisted containers:** `mp4`, `mkv`, `mov`, `avi`, `webm`.

### 2.6 Error Catalog (`errors.py`)

| Domain exception          | HTTP status | Error code            |
|---------------------------|-------------|-----------------------|
| `InvalidInputError`       | 400         | `INVALID_INPUT`       |
| `VideoTooLargeError`      | 413         | `FILE_TOO_LARGE`      |
| `UnsupportedFormatError`  | 422         | `UNSUPPORTED_FORMAT`  |
| `DurationExceededError`   | 422         | `DURATION_EXCEEDED`   |
| `DuplicateVideoError`     | 409         | `DUPLICATE_VIDEO`     |
| `InvalidUrlError`         | 400         | `INVALID_URL`         |
| `UnsupportedHostError`    | 400         | `UNSUPPORTED_HOST`    |
| `VideoNotFoundError`      | 404         | `NOT_FOUND`           |
| `StorageError`            | 500         | `STORAGE_ERROR`       |

Async-only (persisted to the record):
- `DOWNLOAD_FAILED`, `VIDEO_PRIVATE`, `VIDEO_REMOVED`, `VIDEO_AGE_GATED`, `VIDEO_REGION_BLOCKED`

A single decorator in `routes.py` catches domain exceptions and returns the envelope. Routes do not contain try/except for these — they're caught centrally.

### 2.7 Repository (`repository.py`)

Thin async wrapper around the Motor collection. Returns Pydantic `VideoDocument` instances, never raw dicts.

```python
class VideoRepository:
    def __init__(self, db: AsyncIOMotorDatabase): ...
    async def insert(self, doc: VideoDocument) -> VideoDocument: ...
    async def update_status(self, video_id: str, *, status, ...) -> VideoDocument: ...
    async def get_by_id(self, video_id: str) -> VideoDocument | None: ...
    async def find_by_hash(self, content_hash: str) -> VideoDocument | None: ...
    async def list_videos(self, status: VideoStatus | None) -> list[VideoDocument]: ...
    async def delete(self, video_id: str) -> bool: ...
```

Injected via FastAPI `Depends(get_video_repository)`. `get_video_repository` reads the shared Motor client from `app.core.db.client.get_db()`.

### 2.8 yt-dlp Wrapper (`youtube.py`)

```python
def download_to(url: str, target_dir: Path) -> YoutubeResult:
    """Sync. Returns (filename, title, source_url). Raises YoutubeDownloadError."""
```

Options used: `format="best[ext=mp4]/best"`, `outtmpl=str(target_dir / "%(id)s.%(ext)s")`, `noprogress=True`, `quiet=True`. Map yt-dlp exception types to specific error codes:
- `DownloadError` with "Private video" → `VIDEO_PRIVATE`
- `DownloadError` with "Video unavailable" / "has been removed" → `VIDEO_REMOVED`
- `DownloadError` with "Sign in to confirm your age" → `VIDEO_AGE_GATED`
- `GeoRestrictedError` / "not available in your country" → `VIDEO_REGION_BLOCKED`
- Anything else → `DOWNLOAD_FAILED`

Called from `tasks.py` via `await asyncio.to_thread(youtube.download_to, ...)`.

### 2.9 Static File Mount

In `app/main.py`:

```python
from fastapi.staticfiles import StaticFiles
app.mount(
    "/media/thumbnails",
    StaticFiles(directory=settings.media_dir / "thumbnails"),
    name="thumbnails",
)
```

Path is computed at startup. The `media/thumbnails/` directory is created in `lifespan` if missing.

### 2.10 Configuration Additions

New fields in `app/core/config.py`:

| Field                    | Default                                    | Source        |
|--------------------------|--------------------------------------------|---------------|
| `max_file_size_bytes`    | `5 * 1024**3` (5GB)                        | env override  |
| `max_duration_seconds`   | `14400` (4h)                               | env override  |
| `supported_containers`   | `["mp4","mkv","mov","avi","webm"]`         | env override  |
| `allowed_url_hosts`      | `["youtube.com","youtu.be","www.youtube.com","m.youtube.com"]` | env override |

New `@property`:
```python
@property
def thumbnails_dir(self) -> Path:
    return self.media_dir / "thumbnails"
```

`.env.example` updated with the four new variables.

### 2.11 Startup Hardening

In `lifespan`:
- Create `media/originals/`, `media/originals/.tmp/`, `media/thumbnails/` if missing.
- Sweep `media/originals/.tmp/` — any file older than 1 hour at startup is deleted (cleanup of crashed imports).
- Mark any DB record with `status=uploading` and `updated_at` older than 1 hour as `status=failed` with `error_code=INTERRUPTED` (orphans from prior crashes; idempotent — running this on every startup is safe).

---

## 3. Frontend Design

### 3.1 Feature Folder Layout

```
frontend/src/features/import/
├── components/
│   ├── ImportPanel/index.tsx          # 'use client' wrapper hosting both import controls
│   ├── UploadDropzone/index.tsx       # 'use client' drag-drop + file input
│   ├── UrlImportForm/index.tsx        # 'use client' URL input + submit
│   ├── VideoLibrary/index.tsx         # 'use client' SWR data + grid
│   ├── VideoCard/index.tsx            # presentational (server-renderable)
│   ├── StatusFilterChips/index.tsx    # 'use client' filter state
│   ├── StatusChip/index.tsx           # presentational; shared between cards & filter group
│   ├── EmptyState/index.tsx           # presentational
│   └── DeleteConfirmDialog/index.tsx  # 'use client' MUI Dialog
├── hooks/
│   ├── useVideos.ts                   # SWR; conditional 3s polling when any uploading
│   ├── useUploadVideo.ts              # POST multipart; tracks busy state
│   ├── useImportUrl.ts                # POST JSON; triggers SWR revalidate
│   └── useDeleteVideo.ts              # DELETE; optimistic update
├── lib/
│   ├── api.ts                         # endpoint wrappers (typed)
│   └── format.ts                      # formatDuration, formatBytes
└── types.ts                           # generated from Pydantic; gitignored marker
```

Shared-kernel files updated by this chunk (outside the feature folder, required for DESIGN.md conformance):

```
frontend/src/
├── app/
│   ├── layout.tsx                     # swap next/font/google to Hanken Grotesk, Inter, JetBrains Mono
│   └── page.tsx                       # replace placeholder with ImportPanel + VideoLibrary
├── lib/
│   ├── theme.ts                       # reconcile to Vivid Velocity tokens (palette, typography, radii)
│   └── tokens.ts                      # NEW — exports raw Vivid Velocity hex/spacing tokens for theme + sx
└── types/
    └── mui-augment.d.ts               # NEW — MUI module augmentation: extra palette keys & typography variants
```

### 3.2 Route

`frontend/src/app/page.tsx` (replaces the Phase 1 placeholder home page):

```tsx
// Server Component shell
import { ImportPanel } from '@/features/import/components/ImportPanel';
import { VideoLibrary } from '@/features/import/components/VideoLibrary';

export default function HomePage() {
  return (
    <main>
      <ImportPanel />
      <VideoLibrary />
    </main>
  );
}
```

The page itself is a Server Component. Only child components that need interactivity carry `'use client'`. This matches CLAUDE.md's "Never `'use client'` at the page level".

### 3.3 Component Contracts

**`ImportPanel`** — Layout-only wrapper. Renders `UploadDropzone` and `UrlImportForm` side by side on desktop, stacked on mobile.

**`UploadDropzone`** — Drag-over visual feedback. Click opens file picker. On drop/select, calls `useUploadVideo().upload(file)`. Disabled with overlay spinner while busy. Inline error message below the dropzone on rejection (cleared on next interaction).

**`UrlImportForm`** — Text field + submit button. Validates `youtube.com|youtu.be` URLs client-side as a UX nicety (server is still authoritative). On submit, calls `useImportUrl().importUrl(url)`. Clears field on success.

**`VideoLibrary`** — Hosts `StatusFilterChips`, renders `VideoCard` grid via `useVideos(status)`, shows `EmptyState` when `videos.length === 0` and no filter active. Loading: MUI `Skeleton` grid (6 cards). Error: inline alert with retry button.

**`VideoCard`** — Props: `video: VideoDocument`. Renders:
- 16:9 thumbnail (`<img src={video.thumbnail_url}>` with `next/image` fallback). Placeholder block while `status=uploading`. Absolute-positioned `StatusChip` top-left, duration mono-pill bottom-right.
- Below thumbnail: title (`title-md`, one-line truncate), file size in `code-sm` (JetBrains Mono), created date in `body-sm` muted (`onSurfaceVariant`).
- Delete `IconButton` (Lucide `Trash2`, 20px) in top-right of metadata row → opens `DeleteConfirmDialog`.
- `status=failed` shows `error_message` in `error` color below meta as `body-sm`.
- Mid-level glassmorphic surface, 16px radius (Content object per DESIGN.md). Border illuminates to `primaryContainer` @ 60% on hover (180ms standard ease-out, disabled when `prefers-reduced-motion`).

**`StatusFilterChips`** — MUI `Chip` set: All | Uploading | Imported | Failed. Controlled via local state, passed up to `VideoLibrary` via context or props. (Simple prop passing for 2A — no feature-level context provider yet.)

**`EmptyState`** — Icon + heading + body copy pointing at the import panel above.

**`DeleteConfirmDialog`** — MUI `Dialog`. "Delete \"{title}\"? This removes the file from disk." Cancel + Delete buttons. On confirm, calls `useDeleteVideo().delete(id)`, then closes.

### 3.4 Data Layer (Hooks)

**`useVideos(status?: VideoStatus)`:**
```ts
const { data, error, isLoading, mutate } = useSWR(
  ['videos', status],
  ([, s]) => api.get(`/api/videos${s ? `?status=${s}` : ''}`),
  { refreshInterval: hasUploading ? 3000 : 0 }
);
```
The `hasUploading` flag derives from the current `data` so polling only runs while needed. Other mutations (`useUploadVideo`, `useImportUrl`, `useDeleteVideo`) call `mutate` to refresh.

**`useUploadVideo`:**
- Uses native `fetch` with `FormData`. No progress (2A scope — busy state only). 2B will swap to `XMLHttpRequest` for upload progress and WebSocket for backend processing progress.
- Returns `{ upload, isUploading, error, reset }`.

**`useImportUrl`:**
- POSTs JSON. On 202, calls `mutate` so the placeholder card appears immediately.
- Returns `{ importUrl, isImporting, error, reset }`.

**`useDeleteVideo`:**
- Optimistic update: removes the card from cache, then DELETEs. Restores on failure.
- Returns `{ delete, isDeleting, error }`.

### 3.5 Type Generation

A backend script generates TypeScript from the feature's Pydantic schemas. CLAUDE.md mandates this — no hand-mirrored types.

`backend/scripts/generate_ts.py`:
```python
# Walk app.features.*.schemas, collect BaseModel subclasses,
# emit to frontend/src/features/{feature}/types.ts
# Uses pydantic-to-typescript (third-party) or hand-rolled JSON Schema → TS.
```

Choice: use `pydantic-to-typescript` (mature, single dep). Add to backend dev deps. Output file header includes `// AUTO-GENERATED — do not edit. Run: uv run python -m scripts.generate_ts`.

Workflow:
1. Backend devs edit `schemas.py`.
2. Run `uv run python -m scripts.generate_ts` (also wired into a pre-commit hook eventually).
3. Frontend imports from `@/features/import/types`.

### 3.6 API Wrapper Additions

The existing `frontend/src/lib/api.ts` handles JSON envelope unwrapping. It does NOT handle multipart. Extend with:

```ts
export async function uploadFile<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append('file', file);
  // Note: do NOT set Content-Type; browser sets multipart boundary automatically.
  // Bypass the JSON-only `request()` wrapper.
}
```

Same envelope-unwrapping semantics as `request()`.

### 3.7 Styling & Design System Conformance

**Phase 1 placeholder theme is non-conforming.** The current `theme.ts` uses Geist fonts, a cyan secondary, and dual light+dark schemes. PRD v1.1 mandates conformance to DESIGN.md (Vivid Velocity). This chunk reconciles the theme as a shared-kernel update before any import component is written.

**`frontend/src/lib/tokens.ts` (new):** Exports raw Vivid Velocity values as plain const objects. This is the single source for hex literals in the frontend codebase — no other file may contain a hex code.

```ts
export const colors = {
  surface: '#131315',
  surfaceContainerLowest: '#0e0e10',
  surfaceContainerLow: '#1b1b1d',
  surfaceContainer: '#201f21',
  surfaceContainerHigh: '#2a2a2c',
  surfaceContainerHighest: '#353437',
  onSurface: '#e5e1e4',
  onSurfaceVariant: '#d0c2d5',
  outline: '#998d9e',
  outlineVariant: '#4d4353',
  primary: '#e0b6ff',
  onPrimary: '#4c007d',
  primaryContainer: '#9d4edd',
  onPrimaryContainer: '#fffdff',
  secondary: '#41ee8d',
  onSecondary: '#00391b',
  secondaryContainer: '#00d174',
  onSecondaryContainer: '#00532b',
  error: '#ffb4ab',
  onError: '#690005',
  errorContainer: '#93000a',
  onErrorContainer: '#ffdad6',
  // ...all DESIGN.md frontmatter values, mechanically transcribed
} as const;

export const spacing = { base: 8, xs: 4, sm: 12, md: 24, lg: 48, xl: 80, gutter: 20 } as const;
export const radii = { sm: 4, default: 8, md: 12, lg: 16, xl: 24, full: 9999 } as const;
```

**`frontend/src/lib/theme.ts` (rewritten):**

```ts
import { createTheme } from '@mui/material/styles';
import { colors, radii } from '@/lib/tokens';

export const theme = createTheme({
  cssVariables: true,
  colorSchemes: { dark: true },          // dark only, no light scheme
  palette: {
    mode: 'dark',
    primary: { main: colors.primaryContainer, contrastText: colors.onPrimaryContainer },
    secondary: { main: colors.secondaryContainer, contrastText: colors.onSecondaryContainer },
    error: { main: colors.errorContainer, contrastText: colors.onErrorContainer },
    background: { default: colors.surface, paper: colors.surfaceContainerLow },
    text: { primary: colors.onSurface, secondary: colors.onSurfaceVariant },
    divider: colors.outlineVariant,
  },
  shape: { borderRadius: radii.default },
  typography: {
    fontFamily: 'var(--font-hanken-grotesk), system-ui, sans-serif',
    h1: { fontFamily: 'var(--font-hanken-grotesk)', fontSize: 48, fontWeight: 800, lineHeight: '56px', letterSpacing: '-0.02em' },      // display-lg
    h2: { fontFamily: 'var(--font-hanken-grotesk)', fontSize: 32, fontWeight: 700, lineHeight: '40px', letterSpacing: '-0.01em' },      // headline-lg
    h3: { fontFamily: 'var(--font-hanken-grotesk)', fontSize: 20, fontWeight: 600, lineHeight: '28px' },                                  // title-md
    body1: { fontFamily: 'var(--font-inter)', fontSize: 16, fontWeight: 400, lineHeight: '24px' },                                        // body-lg
    body2: { fontFamily: 'var(--font-inter)', fontSize: 14, fontWeight: 400, lineHeight: '20px' },                                        // body-sm
    overline: { fontFamily: 'var(--font-jetbrains-mono)', fontSize: 12, fontWeight: 600, lineHeight: '16px', letterSpacing: '0.05em', textTransform: 'uppercase' }, // label-caps
    button: { fontFamily: 'var(--font-inter)', fontSize: 14, fontWeight: 600, textTransform: 'none' },
  },
});
```

**`frontend/src/types/mui-augment.d.ts` (new):** Extends MUI's typography and palette types so `<Typography variant="labelCaps">` and `theme.palette.surfaceContainer.high` are type-safe. Adds:
- Typography variants: `labelCaps`, `codeSm`, `displayLg` (mapped to overline/caption/h1 in the theme above if MUI keys overflow, OR added as custom variants via `typography.variants` extension).
- Palette extensions: `surfaceContainer.{lowest,low,default,high,highest}`, `outline`, `outlineVariant`, `onSurfaceVariant`, `primaryContainer`, `secondaryContainer`, `errorContainer`, etc.

**`frontend/src/app/layout.tsx` (font swap):**

```ts
import { Hanken_Grotesk, Inter, JetBrains_Mono } from 'next/font/google';

const hanken = Hanken_Grotesk({ variable: '--font-hanken-grotesk', subsets: ['latin'], weight: ['600', '700', '800'] });
const inter = Inter({ variable: '--font-inter', subsets: ['latin'], weight: ['400', '500', '600'] });
const jetbrains = JetBrains_Mono({ variable: '--font-jetbrains-mono', subsets: ['latin'], weight: ['400', '600'] });

// <html className={`${hanken.variable} ${inter.variable} ${jetbrains.variable}`}>
```

Existing Geist imports are removed; `--font-geist-sans` / `--font-geist-mono` CSS vars are no longer referenced anywhere.

**Status chip color mapping (per PRD §UI/UX Direction):**

| Status      | Background                              | Text/Dot                  | MUI prop                                                |
|-------------|------------------------------------------|---------------------------|---------------------------------------------------------|
| `uploading` | `primaryContainer` @ 24% alpha           | `primary` token           | `<Chip color="primary" variant="filled" />` + custom alpha |
| `imported`  | `secondaryContainer` @ 24% alpha         | `secondary` token         | `<Chip color="secondary" variant="filled" />` + custom alpha |
| `failed`    | `errorContainer` @ 24% alpha             | `error` token             | `<Chip color="error" variant="filled" />` + custom alpha |

Use a single shared `StatusChip` component (`features/import/components/StatusChip/index.tsx`) that takes `status: VideoStatus` and returns the correctly tokenized MUI Chip. No per-call sx prop tweaking.

**Glassmorphic surfaces (per DESIGN.md "Mid Level" recipe):**

Implemented via a styled wrapper or shared `sx` recipe in `features/import/lib/surfaces.ts`:

```ts
export const midSurface = {
  bgcolor: 'rgba(32, 31, 33, 0.8)',         // surfaceContainer @ 80%
  border: '1px solid',
  borderColor: 'rgba(255, 255, 255, 0.08)',  // outline at low opacity per DESIGN.md
  backdropFilter: 'blur(20px)',
  borderRadius: radii.md,                    // 12px for panels
};
export const highSurface = {
  ...midSurface,
  backdropFilter: 'blur(20px)',
  boxShadow: `0 0 0 1px rgba(157, 78, 221, 0.15)`, // subtle Primary glow per DESIGN.md High Level
};
```

Cards (Content objects) use `radii.lg` (16px); buttons/inputs (UI controls) use `radii.default` (8px) — per DESIGN.md Shapes section.

**Hover-illuminate border on VideoCard:**

```ts
sx={{
  ...midSurface,
  borderRadius: radii.lg,
  transition: 'border-color 180ms cubic-bezier(0.4, 0, 0.2, 1)',
  '&:hover': { borderColor: 'rgba(157, 78, 221, 0.6)' }, // primaryContainer @ 60%
  '@media (prefers-reduced-motion: reduce)': { transition: 'none' },
}}
```

**Grid:**

MUI `Grid` v2: `<Grid container spacing={spacing.gutter / 8}>` (gutter token = 20px → MUI spacing 2.5). Card breakpoint: `xs={12} sm={6} md={4} lg={3}` (1/2/3/4 columns).

**No hardcoded hex values anywhere outside `tokens.ts`.** Lint rule (a Vitest custom test or ESLint plugin) verifies this.

---

## 4. Testing Strategy

Test-first per CLAUDE.md. First file in each new folder is the test file.

### 4.1 Backend (pytest)

**Fixtures (`tests/conftest.py`):**
- `sample_mp4` — 5s 320x240 H.264 silent MP4 (~30KB), committed to `tests/fixtures/`.
- `sample_mkv` — 3s MKV variant.
- `audio_only_mp4` — MP4 with only an audio stream.
- `oversize_marker` — `Settings(max_file_size_bytes=1024)` override for size-limit tests.
- `test_db` — Motor connection to `ai_clipper_test` DB, dropped after each test.
- `app_client` — `httpx.AsyncClient(app=app, base_url="http://test")` with the test DB.

**Test files map to acceptance criteria:**

| Test | AC covered |
|------|-----------|
| `test_upload_mp4_returns_imported_record` | Story 1 |
| `test_upload_mkv_succeeds` | Story 1 |
| `test_upload_rejects_audio_only_file` | Story 1 (unsupported codec) |
| `test_upload_rejects_oversize_file` | Story 1 (5GB cap) |
| `test_upload_rejects_long_duration` | Story 1 (4hr cap) |
| `test_upload_rejects_duplicate_hash` | Story 5 |
| `test_upload_sanitizes_filename` | (security: path traversal) |
| `test_url_import_rejects_vimeo_host` | Story 2 (unsupported host) |
| `test_url_import_creates_uploading_record` | Story 2 |
| `test_url_import_background_task_marks_failed_on_dns_error` | Story 2 (network failure) |
| `test_list_videos_returns_newest_first` | Story 3 |
| `test_list_videos_filters_by_status` | Story 3 |
| `test_delete_removes_record_and_file` | Story 4 |
| `test_delete_returns_404_when_missing` | Story 4 (idempotency) |
| `test_delete_idempotent_when_already_deleted` | Story 4 |

YouTube live-network tests marked `@pytest.mark.slow` and `@pytest.mark.network` — excluded from default runs. Default suite uses ffmpeg fixtures + mocked yt-dlp.

**Coverage target:** 90%+ on `service.py`, `media.py`, `youtube.py`, `repository.py`. No gate on `routes.py` (thin glue) or `tasks.py` (background runner, integration-tested via `test_url_import_background_task_*`).

### 4.2 Frontend (Vitest + Playwright)

**Vitest unit tests:**
- `hooks/useVideos.test.ts` — polling behavior toggles on `uploading` presence
- `hooks/useDeleteVideo.test.ts` — optimistic update + rollback on error
- `components/VideoCard/VideoCard.test.tsx` — renders title/duration/size; delete button wired; hover border style applied
- `components/StatusChip/StatusChip.test.tsx` — each status renders with the correct DESIGN.md token (verified by reading inline style / className token, not hex string)
- `lib/format.test.ts` — `formatDuration(45)` → `"0:45"`, `formatBytes(5_368_709_120)` → `"5.0 GB"`
- `components/UrlImportForm/UrlImportForm.test.tsx` — client-side host validation

**Design conformance tests (shared kernel):**
- `lib/tokens.test.ts` — `tokens.colors` matches DESIGN.md frontmatter values exactly (parse the YAML frontmatter, compare keys + hexes; fails loud if `DESIGN.md` drifts from `tokens.ts`).
- `lib/theme.test.ts` — `theme.palette.primary.main === tokens.colors.primaryContainer`; typography variants exist; `colorSchemes.light` is undefined.
- ESLint rule (custom) or Vitest grep test: no hex codes (`/#[0-9a-fA-F]{3,8}\b/`) appear in any file under `src/` except `tokens.ts`.

**Playwright E2E:**
- `e2e/video-import.spec.ts`:
  - Upload a fixture MP4 → card appears in library
  - Delete the card → card disappears
  - Submit a fake YouTube URL with mocked backend → placeholder card appears with `uploading` status, then `imported` after revalidation

Coverage target: 80% on `features/import/` per CLAUDE.md.

### 4.3 Verification Report (Gate 3)

A table maps each PRD acceptance criterion to one or more tests. Generated at end of implementation. Any unverified criterion blocks Gate 3 approval.

---

## 5. File System Layout (Runtime)

```
media/
├── originals/
│   ├── .tmp/                    # In-progress uploads/downloads (cleaned on startup)
│   ├── {video_id_1}/
│   │   └── my-podcast.mp4
│   └── {video_id_2}/
│       └── interview.mkv
├── thumbnails/
│   ├── {video_id_1}.jpg
│   └── {video_id_2}.jpg
└── logs/                        # Phase 1
```

One subdirectory per video — keeps filename-sanitization collisions impossible across videos and makes deletion a single rmtree.

---

## 6. Migration from Phase 1

| Item                         | Action                                                                 |
|------------------------------|------------------------------------------------------------------------|
| `videos` collection          | Already exists. Add sparse unique index on `contentHash` to `init_db.py`. |
| `media/originals/`           | Exists. Ensure `.tmp/` subdir creation in lifespan.                    |
| `media/thumbnails/`          | New. Create in lifespan.                                               |
| `app/main.py`                | Add import router, static mount, orphan-record cleanup in lifespan.    |
| `app/core/config.py`         | Add four new fields + `thumbnails_dir` property.                       |
| `.env.example`               | Document new vars.                                                     |
| `backend/pyproject.toml`     | Add `yt-dlp`, `python-multipart`, `pydantic-to-typescript` (dev).      |
| `frontend/src/app/page.tsx`  | Replace placeholder home page with `ImportPanel` + `VideoLibrary`.     |
| `frontend/src/app/layout.tsx`| Swap `next/font/google` from Geist/Geist_Mono to Hanken_Grotesk + Inter + JetBrains_Mono. |
| `frontend/src/lib/theme.ts`  | Rewrite against Vivid Velocity tokens; drop light scheme; add typography variants. |
| `frontend/src/lib/tokens.ts` | NEW. Single source for Vivid Velocity hex values + spacing + radii.    |
| `frontend/src/types/mui-augment.d.ts` | NEW. Module augmentation for extra palette keys + typography variants. |
| `frontend/src/features/import/` | Populate (currently empty per Phase 1 scaffold).                    |

No data migration required — there are no production records yet.

---

## 7. Technical Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Streaming multipart with size watchdog has subtle off-by-one allowing >5GB | Med | Med | Check `total_bytes_written + chunk_size > limit` BEFORE writing chunk; integration test with 5GB+1 byte fixture (mocked stream, not real 5GB file). |
| SHA-256 of multi-GB file on hot path adds upload latency | Med | Low | Hash during stream-write (single pass over bytes); no separate read pass. Documented expected cost in code comment. |
| ffprobe missing on host | Low | High | Phase 1 verified ffmpeg installed via winget. Startup health check verifies `ffprobe -version` succeeds; fail loud on `/health`. |
| yt-dlp output filename collisions | Low | Med | Use `outtmpl="%(id)s.%(ext)s"` (YouTube video ID is unique); plus per-video subdirectory under originals. |
| Background task crashes mid-download → orphan record stuck in `uploading` | Med | Low | Startup sweep marks stale `uploading` records as `failed` with `INTERRUPTED` code. |
| Static file mount serves arbitrary paths if not constrained | Low | High | `StaticFiles(directory=...)` is path-constrained by design; verified via test attempting `..` traversal. |
| Windows path length >260 chars breaks file ops | Low | Low | Per-video subdirectory uses short ObjectId; filename truncated to 200 chars. Combined well under limit. |
| SWR 3s polling thrashes the API when many uploading records | Low | Low | Single endpoint call regardless of record count; 3s is conservative for local single-user app. Replaced by WebSocket in 2B. |
| `pydantic-to-typescript` emits incompatible types for `HttpUrl` | Low | Low | Map `HttpUrl` → `string` manually in the generator config; verified by smoke test in CI. |

---

## 8. Implementation Order (TDD-Friendly)

Each step delivers one tested unit. No step depends on later steps for correctness.

1. **Schemas + errors** — `schemas.py`, `errors.py`. Tests: enum round-trip, model serialization. (Trivial; lays the contract.)
2. **Repository** — `repository.py` + `test_repository.py`. Tests against test DB: insert, get_by_id, find_by_hash, list_videos, update_status, delete.
3. **Media probe + thumbnail + hash** — `media.py` + `test_media.py`. Tests against fixture videos: probe extracts duration & container, thumbnail produces valid JPEG, hash matches `sha256sum` of fixture.
4. **Init DB index migration** — update `scripts/init_db.py`. Test: re-run is idempotent; index appears in `index_information()`.
5. **Config additions** — extend `core/config.py`. Tests: env override parses correctly.
6. **Service: upload path** — `service.import_uploaded_file` + service tests with mocked repo. Tests cover all rejection paths and happy path.
7. **Routes: upload** — `routes.py` upload handler + integration test through `httpx.AsyncClient`. Test: 201 on valid, 413 on oversize, 422 on bad format, etc.
8. **YouTube wrapper** — `youtube.py` + `test_youtube.py` (mocked yt-dlp). Tests: each exception type maps to correct error code.
9. **Service: URL import + background task** — `service.import_from_url`, `tasks.download_youtube` + tests with mocked youtube wrapper.
10. **Routes: URL import** — `routes.py` URL handler + integration test.
11. **Routes: list + delete** — same file + tests.
12. **Static file mount + lifespan additions** — `app/main.py` updates + test that thumbnail URL returns 200.
13. **TS type generation script** — `scripts/generate_ts.py`. Test: running it produces a non-empty TS file with expected interfaces.
14. **Design system reconciliation (shared kernel)** — create `lib/tokens.ts`, rewrite `lib/theme.ts` against Vivid Velocity, add `types/mui-augment.d.ts`, swap fonts in `app/layout.tsx`. Tests: `tokens.test.ts` (matches DESIGN.md), `theme.test.ts` (Vivid Velocity wired correctly, dark-only). This is a prerequisite for every frontend component step below — done first so all components can consume final tokens.
15. **Frontend hooks** — `useVideos`, `useUploadVideo`, `useImportUrl`, `useDeleteVideo` + Vitest tests.
16. **Frontend lib** — `api.ts` `uploadFile` extension, `format.ts` + tests, `surfaces.ts` (glassmorphic recipes).
17. **Frontend components** — `StatusChip` (shared), then `VideoCard`, `StatusFilterChips`, `EmptyState` (presentational, easy tests), then `UploadDropzone`, `UrlImportForm`, `VideoLibrary`, `DeleteConfirmDialog`, `ImportPanel`.
18. **Home page** — replace `app/page.tsx`.
19. **No-hex lint guard** — custom ESLint rule (or Vitest pattern test) prohibiting hex codes outside `tokens.ts`. Wire into `pnpm lint`.
20. **Playwright E2E** — `e2e/video-import.spec.ts` covering golden path.
21. **Verification Report** — generate the AC-to-test matrix (including the PRD Design Compliance Checklist), file as Gate 3 artifact.

Atomic commits per step (Conventional Commits). Step numbers map cleanly to commit subjects: `feat(import): add video schemas and domain errors`, etc.

---

## 9. Open Questions for Tech Lead Review

**One flagged drift:** Phase 1's `theme.ts` and `app/layout.tsx` were placeholder/non-conforming (Geist fonts, cyan secondary, dual light+dark schemes). This chunk reconciles them to DESIGN.md as a shared-kernel update — see §3.7 and step 14 of §8. Tech Lead should confirm this scope expansion is acceptable; the alternative is to ship visually-inconsistent components in 2A and reconcile in 2B, which violates the CLAUDE.md "Visual coherence" guardrail.

If the reviewer disagrees on:
- **Subprocess vs `ffmpeg-python`** — switch to `ffmpeg-python` is a 30-min change; we chose subprocess for native asyncio.
- **Per-video subdirectory** — could use flat `originals/{video_id}.{ext}` instead. Subdir was chosen for deletion simplicity and filename-collision safety.
- **3s polling vs immediate WebSocket** — WebSocket is explicitly scoped to 2B per `phase-2-chunking.md`. Polling is the 2A bridge.
- **MUI custom variants vs reusing built-ins** — `label-caps` could be `Typography.overline` with custom letterSpacing rather than a new variant. We chose new variants for DESIGN.md fidelity; reusing built-ins reduces module augmentation surface.
- **No-hex lint rule as Vitest test vs ESLint plugin** — Vitest pattern test is zero-dep and runs in CI; ESLint plugin gives in-editor feedback. We can do both; Vitest first since it's faster to author.

---

## 10. Definition of Done

This document is implemented when:
- All 21 implementation steps complete with passing tests.
- `uv run pytest` green, 90%+ coverage on target modules.
- `pnpm vitest run` green, 80%+ coverage on `features/import/` and the new shared-kernel design files (`lib/tokens.ts`, `lib/theme.ts`).
- `pnpm playwright test e2e/video-import.spec.ts` green.
- No-hex lint guard green: no hex codes anywhere under `frontend/src/` except `tokens.ts`.
- Manual run-through of the 10 Verification scenarios from the PRD succeeds — including the PRD Design System Compliance Checklist (every box ticked).
- Verification Report committed to `docs/features/video-import/video-import-verification.md`.
- User approves Gate 3.
