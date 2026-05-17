# Technical Design Document: Transcription Pipeline + WebSocket Progress

**Feature:** Transcription Pipeline (Phase 2, Chunk 2B)
**Version:** 1.0
**Date:** 2026-05-17
**Author:** Tech Lead
**Implements:** `transcription-pipeline-prd.md` (v1.0, approved)
**Depends on:** Chunk 2A merged. Phase 1 model loader stubs (`app/core/models/loader.py`), WebSocket placeholder (`app/main.py`), and `app/workers/` empty package are evolved into real implementations here.

---

## 1. Architecture Overview

```
┌──────────────────────────────────────┐         ┌──────────────────────────────────────────────────────┐
│  Browser (Next.js 16)                │         │  FastAPI Backend (single uvicorn worker)             │
│  features/import/ (extended)         │  HTTP   │  features/transcription/                             │
│  ┌──────────────────────────────┐    │ ──────▶ │  ┌──────────────────────────────┐                    │
│  │ VideoCard (extended)         │    │ REST    │  │ routes.py                    │                    │
│  │   ├ ProgressOverlay (new)    │    │         │  │   POST /api/videos/{id}/retry│                    │
│  │   ├ QueuePositionPill (new)  │    │         │  │   GET  /api/videos/{id}/transcript                │
│  │   └ RetryButton  (new)       │    │         │  └──────────────┬───────────────┘                    │
│  │ StatusChip (extended enum)   │    │         │                 ▼                                    │
│  └──────────────────────────────┘    │         │  ┌──────────────────────────────┐                    │
│  lib/ (shared kernel)                │         │  │ service.py                   │                    │
│  ┌──────────────────────────────┐    │  WS     │  │   retry_transcription        │                    │
│  │ useTranscriptionProgress(id) │    │ ◀─────▶ │  │   get_transcript             │                    │
│  │   ├ snapshot handling        │    │         │  └──────────────────────────────┘                    │
│  │   ├ reconnect w/ backoff     │    │         │  ┌──────────────────────────────┐                    │
│  │   └ progress event reducer   │    │         │  │ repository.py                │                    │
│  └──────────────────────────────┘    │         │  │   TranscriptRepository       │                    │
│                                      │         │  │   (extends VideoRepository   │                    │
│                                      │         │  │    with transcription fields)│                    │
│                                      │         │  └──────────────────────────────┘                    │
│                                      │         │  ┌──────────────────────────────┐                    │
│                                      │         │  │ whisper.py                   │                    │
│                                      │         │  │   transcribe(audio_path,     │                    │
│                                      │         │  │              on_segment)     │                    │
│                                      │         │  └──────────┬───────────────────┘                    │
│                                      │         │             │ uses                                   │
│                                      │         │             ▼                                        │
│                                      │         │  ┌────────────────────────────────────────────────┐  │
│                                      │         │  │ core/models/loader.py — load_whisper_medium()  │  │
│                                      │         │  │ (Phase 1 stub now wires faster-whisper)        │  │
│                                      │         │  └────────────────────┬───────────────────────────┘  │
│                                      │         │                       │                              │
│                                      │         │  ┌────────────────────▼──────────┐                   │
│                                      │         │  │ core/gpu/vram.py              │  ← shared kernel  │
│                                      │         │  │   assert_available(bytes)     │     (chunk 3      │
│                                      │         │  │   via pynvml                  │      reuses)      │
│                                      │         │  └───────────────────────────────┘                   │
│                                      │         │                                                      │
│  workers/                            │         │  workers/transcription.py — coordinator loop         │
│                                      │         │  ┌────────────────────────────────────────────────┐  │
│                                      │         │  │ async def run_forever():                       │  │
│                                      │         │  │   while True:                                  │  │
│                                      │         │  │     v = await pickup_next_queued()             │  │
│                                      │         │  │     if v is None:                              │  │
│                                      │         │  │       await sleep(POLL_INTERVAL); continue    │  │
│                                      │         │  │     await transcribe_video(v)                  │  │
│                                      │         │  └────────────────────────────────────────────────┘  │
│                                      │         │                                                      │
│                                      │         │  core/ws/ — WS connection manager                    │
│                                      │         │  ┌────────────────────────────────────────────────┐  │
│                                      │         │  │ manager.subscribe(video_id, websocket)         │  │
│                                      │         │  │ manager.broadcast(video_id, event)             │  │
│                                      │         │  │ manager.disconnect(video_id, websocket)        │  │
│                                      │         │  └────────────────────────────────────────────────┘  │
│                                      │         └─────────────────────────────────┬────────────────────┘
│                                      │                                           │
│                                      │                                           ▼
│                                      │                                    ┌─────────────────────┐
│                                      │                                    │  MongoDB            │
│                                      │                                    │   videos (extended) │
│                                      │                                    │   transcripts (new) │
│                                      │                                    └─────────────────────┘
│                                      │                                    ┌─────────────────────┐
│                                      │                                    │  Filesystem         │
│                                      │                                    │   models/whisper-…  │
│                                      │                                    │   media/originals/  │
│                                      │                                    └─────────────────────┘
└──────────────────────────────────────┘
```

**Lifecycle (happy path):**
1. User imports video (2A flow) → record reaches `status=imported`.
2. 2A's import service calls `coordinator.enqueue(video_id)` after the successful import write. This is a one-line addition to 2A's `service.import_uploaded_file` and `tasks.download_youtube` happy paths.
3. `enqueue` flips status `imported → queued` (atomic `findOneAndUpdate` with status precondition).
4. Worker loop (started in lifespan) picks up the queued video via atomic `findOneAndUpdate` `{status: queued} → {status: transcribing, transcriptionStartedAt: now}`, ordered by `createdAt asc`.
5. Worker calls `whisper.transcribe(storage_path, on_segment=publish_progress)`.
6. `publish_progress(segment)` updates `lastProgressPercent` on the video record and broadcasts a `progress` event via the WS manager keyed by `video_id`.
7. On completion, worker writes the full transcript to the `transcripts` collection (one atomic insert), flips video `status=ready`, broadcasts `complete`, closes any subscribed WS connections.
8. Loop continues with next `queued` video, or sleeps `POLL_INTERVAL_SEC` if none.

**Lifecycle (failure):** Whisper raises → worker catches, flips video `status=failed` with `errorCode=TRANSCRIPTION_FAILED` / `AUDIO_DECODE_FAILED`, broadcasts `error` event with code + message, queue advances.

**Lifecycle (restart):** Lifespan startup → sweep `{status: transcribing}` records → flip back to `queued`. Worker loop starts. Any `imported` records left from before 2B deploy also get enqueued by a one-shot back-fill sweep.

**Concurrency model:** Single uvicorn worker process (already required for VRAM constraint per `CLAUDE.md`). Single in-process worker task. Sequential FIFO is natural — there is no parallelism to coordinate.

---

## 2. Backend Design

### 2.1 Feature Folder Layout

```
backend/app/features/transcription/
├── __init__.py
├── routes.py                 # FastAPI APIRouter — retry endpoint, transcript GET
├── service.py                # Domain operations (retry, get_transcript, fail_with_error)
├── repository.py             # TranscriptRepository (transcripts collection)
│                             # Plus extension methods on VideoRepository for status transitions
├── schemas.py                # Pydantic: TranscriptDocument, Segment, Word, ProgressEvent, etc.
├── errors.py                 # Domain exceptions + error code enum
├── whisper.py                # faster-whisper wrapper, sync→async via to_thread
├── coordinator.py            # enqueue(), pickup_next_queued(), back-fill sweep
└── tests/
    ├── __init__.py
    ├── conftest.py           # fixtures: short audio file, mock Whisper model
    ├── test_routes.py        # retry endpoint, transcript GET
    ├── test_service.py       # retry state transitions
    ├── test_repository.py    # transcript CRUD against test DB
    ├── test_whisper.py       # @pytest.mark.slow — real Whisper run against fixture audio
    ├── test_coordinator.py   # enqueue, pickup race conditions, sweep
    └── test_schemas.py       # Pydantic round-trips, ProgressEvent envelope
```

Plus shared-kernel additions outside the feature folder:

```
backend/app/core/gpu/
├── __init__.py
├── vram.py                   # pynvml wrapper: assert_available(bytes), snapshot()
└── tests/
    └── test_vram.py          # mocked pynvml: budget pass/fail; no pynvml installed → graceful

backend/app/core/ws/
├── __init__.py
├── manager.py                # ConnectionManager class (subscribe/broadcast/disconnect)
├── routes.py                 # /ws/{video_id} endpoint (replaces app/main.py placeholder)
├── schemas.py                # WS message envelope, event type discriminator
└── tests/
    └── test_manager.py       # subscribe/broadcast/multi-subscriber/disconnect

backend/app/workers/
├── __init__.py
├── transcription.py          # WorkerLoop class: lifespan-managed task
└── tests/
    └── test_transcription.py # loop start/stop, processes queue, idle when empty
```

Wired into `app/main.py`:
- `app.include_router(ws_routes.router)` — replaces the existing `@app.websocket("/ws/{job_id}")` placeholder.
- `app.include_router(transcription_routes.router, prefix="/api")`.
- Lifespan additions: register exception handlers, start `WorkerLoop`, run startup sweep.

### 2.2 Data Model

**Extension to `videos` collection (delta from 2A):**

| Field added | Type | Notes |
|---|---|---|
| `status` | enum | Enum extended with: `queued`, `transcribing`, `ready`. Existing `uploading`, `imported`, `failed` retained. |
| `lastProgressPercent` | int? | 0–100. Updated during transcription. Survives restart so the "picking up where we left off" hint can render. Null until first segment completes. |
| `transcriptionStartedAt` | datetime? | Set when status flips to `transcribing`. Null otherwise. Used by sweep timeout heuristic. |
| `transcriptionFinishedAt` | datetime? | Set when status flips to `ready` or `failed`. |
| `errorCode` | string? | Already exists from 2A. Reused — new codes added (see §2.6). |
| `errorMessage` | string? | Already exists from 2A. Reused. |
| `restartedAt` | datetime? | Set by the startup sweep when a `transcribing` record is auto-requeued. Cleared on next successful completion. Frontend uses presence-within-last-30s to render the "picking up where we left off" hint. |

No new indexes are required immediately — the existing `status` index covers `findOneAndUpdate({status: "queued"}, sort: createdAt asc)`. We add one new compound index for the sweep: `{status: 1, transcriptionStartedAt: 1}` to make the optional timeout sweep fast.

**New `transcripts` collection:**

| Field | Type | Notes |
|---|---|---|
| `_id` | ObjectId | Mongo primary key. Independent from `videoId`. |
| `videoId` | string | FK to `videos._id`. Indexed unique — one transcript per video. |
| `language` | string | Whisper auto-detected language code (e.g., `"en"`). |
| `languageProbability` | float | Whisper confidence in language detection (0.0–1.0). |
| `durationSec` | float | Total audio duration as Whisper saw it. |
| `modelName` | string | Whisper model identifier (`"medium"`). For future debug + re-transcribe decisions. |
| `modelVersion` | string | CTranslate2 / faster-whisper version + compute type (`"float16"`). |
| `segments` | array | Array of segment documents (see below). |
| `createdAt` | datetime | UTC. |

**Segment subdocument:**

| Field | Type | Notes |
|---|---|---|
| `start` | float | Segment start in seconds. |
| `end` | float | Segment end in seconds. |
| `text` | string | Concatenated segment text (Whisper's segment-level rendition). |
| `avgLogprob` | float | Diagnostic; not exposed in default API response. |
| `noSpeechProb` | float | Diagnostic; not exposed in default API response. |
| `words` | array | Array of word subdocuments. |

**Word subdocument:**

| Field | Type | Notes |
|---|---|---|
| `word` | string | The recognized token (Whisper includes leading space — preserved as-is for client to render). |
| `start` | float | Word start in seconds. |
| `end` | float | Word end in seconds. |
| `probability` | float | Per-word confidence 0.0–1.0. |

**Why a separate `transcripts` collection (not embedded on `videos`):**

A 60-minute video with normal speech density produces ~9,000 words × ~6 fields/word + segments overhead ≈ ~3MB JSON. At the 4-hour video cap (per 2A) that grows to ~12MB. The 16MB BSON limit is within reach, and embedding a 12MB document on `videos` would balloon every `list_videos` query response in 2A. Separating gives us:
- Cheap library list queries (no transcript join unless requested)
- Future support for partial/streaming transcript reads
- Clean delete-cascade (separate document, separate lifecycle)

**Schema migration (2A → 2B):** No data migration required. Existing `imported` records will be picked up by the back-fill sweep on first 2B boot. New status enum values are additive — any 2A reader of `status` would not encounter the new values for pre-existing data until after this chunk runs.

`scripts/init_db.py` is updated to:
- Add `transcripts` collection with unique index on `videoId`.
- Add `{status: 1, transcriptionStartedAt: 1}` compound index on `videos`.

Idempotent re-run is safe (already the pattern from 2A).

**Pydantic models (`schemas.py`):**

```python
class VideoStatus(StrEnum):
    UPLOADING = "uploading"
    IMPORTED = "imported"
    QUEUED = "queued"          # new
    TRANSCRIBING = "transcribing"  # new
    READY = "ready"            # new
    FAILED = "failed"

class Word(BaseModel):
    word: str
    start: float
    end: float
    probability: float

class Segment(BaseModel):
    start: float
    end: float
    text: str
    avg_logprob: float = Field(alias="avgLogprob", serialization_alias="avgLogprob")
    no_speech_prob: float = Field(alias="noSpeechProb", serialization_alias="noSpeechProb")
    words: list[Word]

class TranscriptDocument(BaseModel):
    id: str = Field(validation_alias="_id", serialization_alias="id")
    video_id: str = Field(alias="videoId")
    language: str
    language_probability: float = Field(alias="languageProbability")
    duration_sec: float = Field(alias="durationSec")
    model_name: str = Field(alias="modelName")
    model_version: str = Field(alias="modelVersion")
    segments: list[Segment]
    created_at: datetime = Field(alias="createdAt")

class ProgressEvent(BaseModel):
    """Live WebSocket event during transcription."""
    type: Literal["snapshot", "progress", "complete", "error"]
    video_id: str = Field(alias="videoId")
    status: VideoStatus
    percent: int                         # 0–100; null in `complete`/`error` envelopes? always present.
    stage: Literal["transcription"]      # forward-compat for chunk 3+
    segments_done: int | None = Field(alias="segmentsDone", default=None)
    segments_total: int | None = Field(alias="segmentsTotal", default=None)
    elapsed_sec: float = Field(alias="elapsedSec")
    eta_sec: float | None = Field(alias="etaSec", default=None)
    queue_position: int | None = Field(alias="queuePosition", default=None)
    error_code: str | None = Field(alias="errorCode", default=None)
    error_message: str | None = Field(alias="errorMessage", default=None)

class RetryResponse(BaseModel):
    id: str
    status: VideoStatus
```

`VideoStatus` already lives in `features/import/schemas.py` (2A). This chunk **moves** it to `app/core/schemas/video_status.py` (shared kernel) because both `import` and `transcription` features need to import it. The 2A import feature imports it from the new location. No behavioral change.

**Note on serialization aliases:** All API-exposed fields use camelCase via `serialization_alias`, matching the 2A convention. The Pydantic-to-TypeScript codegen carries this through.

### 2.3 API Contracts

All responses use the existing envelope (`{ data, error, meta? }`). New endpoints:

#### `POST /api/videos/{id}/retry`
- **Body:** none.
- **Response 200:** `{ data: { id, status }, error: null }` where `status === "queued"` on success.
- **Errors:**
  - 404 `NOT_FOUND` — video does not exist.
  - 400 `INVALID_INPUT` — id not a valid ObjectId.
  - 409 `INVALID_TRANSITION` — current status is not `failed`. The endpoint is idempotent for already-`queued`/`transcribing`/`ready` cases: it returns 200 with the current status unchanged. Only the truly invalid transitions (e.g., retry on `uploading`) return 409.

#### `GET /api/videos/{id}/transcript`
- **Response 200:** `{ data: TranscriptDocument, error: null }`.
- **Errors:**
  - 404 `NOT_FOUND` — video does not exist, OR video exists but has no transcript yet (e.g., status is `queued` or `transcribing`).
  - 400 `INVALID_INPUT` — id not a valid ObjectId.

Used by Chunk 2C. Exposed in 2B so the contract is in place for 2C's UI to consume without a tech-doc round-trip.

#### `GET /api/videos` (extension)
- The 2A list endpoint already accepts a `status` query param. The expanded enum (`queued`, `transcribing`, `ready`) flows through unchanged.
- One addition: each list item carries the new optional fields (`lastProgressPercent`, `transcriptionStartedAt`, etc.) when relevant.
- No new query params.

#### `WS /ws/{video_id}`
- **Replaces** the Phase 1 placeholder `WS /ws/{job_id}`. The path parameter is renamed `video_id` to reflect that 2B uses videoId as the subscription key (the chunk plan's `{job_id}` wording is forward-looking; we will introduce real jobs in Phase 3 when multi-stage demands it, see §9).
- **Connection lifecycle:**
  1. Client opens `/ws/{video_id}`.
  2. Server validates `video_id` exists. If not → send `error` event with code `JOB_NOT_FOUND`, close.
  3. Server sends `snapshot` event with the current state (status, percent, queue position, etc.).
  4. Server streams `progress` events as transcription advances.
  5. On terminal state (`ready` or `failed`), server sends `complete` or `error` event, then closes the connection.
  6. Client may close at any time; server cleans up subscription via `WebSocketDisconnect` handler.
- **Message envelope:** every message is a `ProgressEvent` (see §2.2). Discriminated by `type`. Client doesn't need to parse free-form data.
- **No client-to-server messages are expected.** The placeholder's echo behavior is removed. Any incoming message is ignored (logged at debug).

### 2.4 Whisper Wrapper (`whisper.py`)

```python
class WhisperService:
    def __init__(self, handle: WhisperHandle):
        self._handle = handle              # already-loaded faster_whisper.WhisperModel

    async def transcribe(
        self,
        audio_path: Path,
        on_segment: Callable[[int, int, Segment], Awaitable[None]],
    ) -> TranscriptionResult: ...
```

**Implementation strategy:**

faster-whisper's `model.transcribe(audio_path, word_timestamps=True)` returns `(segments_iter, info)`. Iterating `segments_iter` triggers segment-by-segment decoding lazily — this is the natural progress hook.

The sync iteration runs in `asyncio.to_thread`. Each segment yielded triggers an async `on_segment` callback via `asyncio.run_coroutine_threadsafe` against the captured event loop. This pattern lets the worker's progress publisher remain async without rewriting Whisper's API.

```python
async def transcribe(self, audio_path, on_segment):
    loop = asyncio.get_running_loop()

    def _sync_on_segment(idx_done: int, total_estimate: int, seg) -> None:
        fut = asyncio.run_coroutine_threadsafe(
            on_segment(idx_done, total_estimate, seg), loop
        )
        fut.result()  # block thread on backpressure; trivially small payload

    def _do_transcribe() -> tuple[list[Segment], Info]:
        segments_iter, info = self._handle.model.transcribe(
            str(audio_path),
            word_timestamps=True,
            vad_filter=True,             # skip silence; faster, fewer empty segments
            beam_size=1,                 # medium model is robust enough; 5 is slow
        )
        # faster-whisper doesn't give us total segments up-front.
        # We estimate via audio_duration / typical_segment_duration (~5s)
        # and refine as we go.
        total_estimate = max(1, int(info.duration / 5.0))
        collected: list[Segment] = []
        for idx, seg in enumerate(segments_iter):
            collected.append(_to_pydantic(seg))
            _sync_on_segment(idx + 1, total_estimate, seg)
        return collected, info

    return await asyncio.to_thread(_do_transcribe)
```

**Loading semantics:**
- The Whisper model is loaded **lazily** on first transcription job, not at startup. This keeps `uv run uvicorn` boot under 5 seconds even with no jobs in the queue.
- Once loaded, `WhisperService` is stored as a module-level singleton (held by the `WorkerLoop`). Subsequent jobs reuse the same model instance.
- VRAM guard runs immediately before the `WhisperModel(...)` constructor call. On failure, the load is not attempted.

**Model load specifics:**
```python
from faster_whisper import WhisperModel

def load_whisper_medium() -> WhisperHandle:
    settings = get_settings()
    path = settings.whisper_medium_path
    _ensure_path(path, "Whisper medium")
    vram.assert_available(settings.whisper_vram_budget_bytes)   # raises on insufficient
    model = WhisperModel(
        model_size_or_path=str(path),
        device="cuda",
        compute_type=settings.whisper_compute_type,             # "float16" per config
        device_index=int(settings.cuda_visible_devices),
    )
    log.info("whisper_medium_loaded", path=str(path))
    return WhisperHandle(name="whisper-medium", path=path, model=model)
```

This replaces the Phase 1 stub. The stub's `WhisperHandle(name=..., path=..., model=None)` is unchanged in shape — only the `model` field becomes non-`None`.

### 2.5 VRAM Guard (`core/gpu/vram.py`)

```python
class VRAMUnavailableError(RuntimeError):
    def __init__(self, requested_bytes: int, available_bytes: int):
        self.requested_bytes = requested_bytes
        self.available_bytes = available_bytes
        super().__init__(
            f"Requested {_human(requested_bytes)} VRAM but only "
            f"{_human(available_bytes)} available"
        )

def snapshot() -> GpuSnapshot:
    """Return current free/used/total VRAM in bytes. Cached for 100ms."""

def assert_available(required_bytes: int) -> None:
    """Raise VRAMUnavailableError if free VRAM < required_bytes + SAFETY_MARGIN."""
```

**Configuration:**

| Setting | Default | Source |
|---|---|---|
| `whisper_vram_budget_bytes` | `2_200 * 1024**2` (2200 MB) | env override `WHISPER_VRAM_BUDGET_MB` |
| `vram_safety_margin_bytes` | `300 * 1024**2` (300 MB) | env override `VRAM_SAFETY_MARGIN_MB` |

**pynvml integration:**

```python
try:
    import pynvml
    _HAS_PYNVML = True
except ImportError:
    _HAS_PYNVML = False
```

If `pynvml` is unavailable (dev machine without CUDA, CI without GPU), `snapshot()` raises `RuntimeError("GPU monitoring unavailable")`. Callers (the Whisper loader) catch this and treat it as a soft-failure-for-tests case: `assert_available` becomes a no-op when `_HAS_PYNVML` is False AND `settings.skip_vram_guard=True`. This is the only env-override path that disables the hard lock — used exclusively in tests.

**The lock is not bypassable in production.** The default for `skip_vram_guard` is `False`; tests set it via fixture.

`pynvml.nvmlInit()` is called once at module import. `nvmlShutdown()` is registered via `atexit`. Subsequent calls are cheap (handle is cached).

**`assert_available` logic:**

```python
def assert_available(required_bytes: int) -> None:
    if not _HAS_PYNVML or get_settings().skip_vram_guard:
        return
    snap = snapshot()
    needed = required_bytes + get_settings().vram_safety_margin_bytes
    if snap.free_bytes < needed:
        raise VRAMUnavailableError(needed, snap.free_bytes)
```

A 100ms TTL cache on `snapshot()` avoids hammering pynvml on rapid checks; not strictly needed for 2B (one check per model load), but cheap insurance for chunk 3.

### 2.6 Error Catalog (`errors.py`)

Domain exceptions raised by `transcription/service.py` and `whisper.py`:

| Domain exception | HTTP status | Error code | Notes |
|---|---|---|---|
| `TranscriptNotFoundError` | 404 | `NOT_FOUND` | GET /transcript |
| `InvalidTranscriptionTransitionError` | 409 | `INVALID_TRANSITION` | Retry on non-`failed` video |
| `TranscriptionFailedError` | 500 | `TRANSCRIPTION_FAILED` | Generic Whisper error |
| `AudioDecodeFailedError` | n/a (worker-only) | `AUDIO_DECODE_FAILED` | Whisper cannot decode the audio (e.g., file is text) |
| `VRAMUnavailableError` | n/a (worker-only) | `VRAM_UNAVAILABLE` | Guard tripped before model load |
| `TranscriptionTimeoutError` | n/a (worker-only) | `TRANSCRIPTION_TIMEOUT` | Wall-clock timeout (default 4× source duration) |

Worker-only errors are caught by the worker loop, persisted to the video record (`errorCode`, `errorMessage`), and broadcast as an `error` WS event. They do not surface as HTTP responses.

### 2.7 Repository (`repository.py`)

```python
class TranscriptRepository:
    def __init__(self, db: AsyncIOMotorDatabase): ...
    async def insert(self, doc: TranscriptDocument) -> TranscriptDocument: ...
    async def get_by_video_id(self, video_id: str) -> TranscriptDocument | None: ...
    async def delete_by_video_id(self, video_id: str) -> bool: ...
```

**Extension methods on the existing `VideoRepository` (2A's class, extended here):**

```python
async def claim_next_queued(self) -> VideoDocument | None:
    """Atomically pick the oldest queued video and flip it to transcribing.
    Returns the claimed document or None if queue is empty."""

async def transition_status(
    self,
    video_id: str,
    *,
    from_status: VideoStatus | set[VideoStatus],
    to_status: VideoStatus,
    set_fields: dict | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> VideoDocument | None:
    """Conditional status update with optional field set. Returns updated doc or None
    if precondition failed (status moved while we were deciding)."""

async def update_progress(
    self,
    video_id: str,
    *,
    percent: int,
) -> None:
    """Hot-path write — lastProgressPercent only. No timestamp bump on this one
    to keep write volume low; updatedAt bumps on status transitions instead."""

async def sweep_stale_transcribing(self) -> list[str]:
    """Return all videos with status=transcribing, flip them to queued,
    set restartedAt=now. Called once at lifespan startup. Returns list of
    affected video_ids for logging."""

async def back_fill_imported(self) -> list[str]:
    """One-shot — find all videos with status=imported and flip to queued.
    Handles 2A records that pre-date 2B's auto-pickup. Called once at lifespan
    startup. Idempotent — subsequent calls find no imported records once
    auto-pickup is wired into 2A's import service."""

async def count_queued_before(self, video_id: str) -> int:
    """Return number of queued videos with earlier createdAt. Used to compute
    queue_position for the snapshot WS event."""
```

`claim_next_queued` uses Motor's `find_one_and_update` with `sort=[("createdAt", 1)]` and `filter={"status": "queued"}` — atomic FIFO consumer.

### 2.8 Coordinator (`coordinator.py`)

Thin module — three functions, no class:

```python
async def enqueue(video_id: str) -> None:
    """Flip imported → queued. Called by 2A's import service on successful import."""
    repo = VideoRepository(get_db())
    await repo.transition_status(
        video_id,
        from_status=VideoStatus.IMPORTED,
        to_status=VideoStatus.QUEUED,
    )

async def retry(video_id: str) -> VideoDocument:
    """Flip failed → queued, clear error. Used by POST /retry."""
    repo = VideoRepository(get_db())
    doc = await repo.transition_status(
        video_id,
        from_status={VideoStatus.FAILED},
        to_status=VideoStatus.QUEUED,
        set_fields={"errorCode": None, "errorMessage": None},
    )
    if doc is None:
        # Either video doesn't exist, or it's already past failed.
        # Distinguish for the caller.
        ...

async def back_fill_at_startup() -> int:
    """Lifespan hook: sweep transcribing → queued, back-fill imported → queued."""
    repo = VideoRepository(get_db())
    swept = await repo.sweep_stale_transcribing()
    bfilled = await repo.back_fill_imported()
    return len(swept) + len(bfilled)
```

**Why a separate module instead of methods on `service.py`:** the coordinator is invoked from multiple callers (import service, retry route, lifespan, worker), and each transition is small enough to be a self-documenting function. A class would force a singleton + DI dance with little benefit.

### 2.9 Worker Loop (`workers/transcription.py`)

```python
class TranscriptionWorker:
    def __init__(self): ...

    async def run_forever(self) -> None: ...
    def cancel(self) -> None: ...
```

**Lifespan integration:**

```python
# in app/main.py lifespan
worker = TranscriptionWorker()
task = asyncio.create_task(worker.run_forever(), name="transcription_worker")
try:
    yield
finally:
    worker.cancel()
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
```

**Loop body:**

```python
async def run_forever(self) -> None:
    settings = get_settings()
    repo = VideoRepository(get_db())
    transcript_repo = TranscriptRepository(get_db())
    self._whisper: WhisperService | None = None

    while not self._cancelled:
        video = await repo.claim_next_queued()
        if video is None:
            await asyncio.sleep(settings.transcription_poll_interval_sec)  # default 2.0
            continue
        try:
            await self._process(video, repo, transcript_repo)
        except Exception as exc:
            log.exception("transcription_unexpected", video_id=video.id)
            await self._fail(video.id, repo, "TRANSCRIPTION_FAILED", str(exc))
```

**`_process(video, ...)`:**

1. Lazy-load Whisper if not already loaded. `VRAMUnavailableError` → fail the video, advance.
2. Define `on_segment(done, total, seg)` closure that:
   - Computes `percent = min(99, int(done / total * 100))` (cap at 99 until complete).
   - Computes ETA via simple linear extrapolation from `elapsed / done * (total - done)`.
   - Writes `update_progress(video.id, percent)`.
   - Broadcasts `ProgressEvent(type="progress", ...)` via WS manager.
   - Throttles to max 1 broadcast per second per video — Whisper occasionally yields segments rapidly during fast-talking audio.
3. Call `whisper.transcribe(video.storage_path, on_segment)`. Wrap in `asyncio.wait_for(..., timeout=4 * video.duration_sec)` for the timeout guard.
4. On success:
   - Build `TranscriptDocument` from segments + info.
   - `transcript_repo.insert(doc)`.
   - `transition_status(video.id, from=TRANSCRIBING, to=READY, set={transcriptionFinishedAt: now})`.
   - Broadcast `complete` event.
5. On `asyncio.TimeoutError` → `_fail(video.id, repo, "TRANSCRIPTION_TIMEOUT", ...)`.
6. On `AudioDecodeFailedError` (Whisper raises a specific exception type for unparseable audio) → `_fail(... "AUDIO_DECODE_FAILED" ...)`.
7. On `VRAMUnavailableError` (caught from the load step) → `_fail(... "VRAM_UNAVAILABLE" ...)`.

**`_fail(...)`:** transition to `FAILED`, set error code/message, broadcast `error` event, set `transcriptionFinishedAt`. The loop continues to next video.

**Throttling implementation:**

```python
class _ThrottledBroadcaster:
    def __init__(self, min_interval_sec: float):
        self._last_emit: dict[str, float] = {}
        self._min = min_interval_sec

    async def maybe_emit(self, video_id: str, event: ProgressEvent) -> None:
        now = time.monotonic()
        last = self._last_emit.get(video_id, 0.0)
        if now - last >= self._min or event.type != "progress":
            self._last_emit[video_id] = now
            await ws_manager.broadcast(video_id, event)
```

`snapshot`, `complete`, and `error` events bypass throttling (always immediate).

### 2.10 WebSocket Manager (`core/ws/manager.py`)

```python
class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(self, video_id: str, ws: WebSocket) -> None: ...
    async def disconnect(self, video_id: str, ws: WebSocket) -> None: ...
    async def broadcast(self, video_id: str, event: ProgressEvent) -> None: ...
    def subscriber_count(self, video_id: str) -> int: ...
```

`broadcast` iterates subscribers, sends `event.model_dump(by_alias=True)`. On individual `WebSocketDisconnect` or generic exception per subscriber, that subscriber is removed; the broadcast continues to the rest. The manager never raises.

**Lifecycle of a connection:**

```python
@router.websocket("/ws/{video_id}")
async def transcription_ws(ws: WebSocket, video_id: str) -> None:
    await ws.accept()
    video = await get_video(video_id)
    if video is None:
        await ws.send_json(error_event("JOB_NOT_FOUND").model_dump(by_alias=True))
        await ws.close()
        return

    snapshot = await build_snapshot(video)
    await ws.send_json(snapshot.model_dump(by_alias=True))

    if video.status in TERMINAL_STATES:
        # Already done — send a final-state event and close.
        final = await build_terminal_event(video)
        await ws.send_json(final.model_dump(by_alias=True))
        await ws.close()
        return

    await ws_manager.subscribe(video_id, ws)
    try:
        while True:
            await ws.receive_text()       # ignore client messages; just hold the connection
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(video_id, ws)
```

`build_snapshot(video)` constructs a `ProgressEvent(type="snapshot", ...)` with the current state. For `queued` videos, includes `queue_position` (computed via `count_queued_before`). For `transcribing`, includes `percent = video.lastProgressPercent or 0`. For `ready`/`failed`, includes the terminal info.

`build_terminal_event(video)` returns either `complete` (ready) or `error` (failed) — used when a client opens a WS for an already-finished job.

### 2.11 Integration with 2A (`features/import/`)

Two one-line additions to 2A's import service:

```python
# in service.import_uploaded_file, after successful insert with status=imported:
from app.features.transcription.coordinator import enqueue
await enqueue(video.id)

# in tasks.download_youtube, after the placeholder is updated to imported:
await enqueue(video_id)
```

These calls are non-blocking from the user's perspective — `enqueue` is a single Mongo write. If `enqueue` fails (transient DB hiccup), the import is still considered successful (the video is at `imported`), and the back-fill sweep on next restart picks it up.

No other 2A code changes.

### 2.12 Configuration Additions (extending `core/config.py`)

| Field | Default | Source |
|---|---|---|
| `whisper_vram_budget_mb` | `2200` | env override |
| `vram_safety_margin_mb` | `300` | env override |
| `skip_vram_guard` | `False` | env override; **test-only** |
| `transcription_poll_interval_sec` | `2.0` | env override |
| `transcription_timeout_multiplier` | `4.0` | env override (timeout = N × source duration) |
| `transcription_progress_throttle_sec` | `1.0` | env override |

Derived properties:
```python
@property
def whisper_vram_budget_bytes(self) -> int:
    return self.whisper_vram_budget_mb * 1024 * 1024

@property
def vram_safety_margin_bytes(self) -> int:
    return self.vram_safety_margin_mb * 1024 * 1024
```

`.env.example` updated with the six new vars.

### 2.13 Logging

Per `CLAUDE.md`, all logs are structured JSON via `structlog`. Required fields: `timestamp`, `level`, `stage`, `job_id` (=`video_id` in this chunk), `message`.

Key log events emitted by this chunk:
- `transcription_enqueued` — coordinator picks up an imported video
- `transcription_claimed` — worker dequeues
- `whisper_model_loaded` — first load (one-time per process)
- `whisper_load_failed_vram` — guard tripped
- `transcription_progress` — debug-level; throttled per video
- `transcription_completed` — successful finish (logs total segments, total words, duration_sec, wall_time_sec)
- `transcription_failed` — terminal failure (logs error_code, error_message)
- `transcription_timeout` — wall-clock timeout
- `startup_sweep_swept` — count of recovered transcribing records
- `startup_sweep_back_filled` — count of imported records back-filled

Log to file via the existing logging setup (already writes JSON to `media/logs/` per Phase 1 lifespan).

### 2.14 Dependency Additions (`backend/pyproject.toml`)

```toml
[project.optional-dependencies]
ai = [
    "faster-whisper>=1.0.3",     # CTranslate2 backend, float16 + word_timestamps
    "pynvml>=11.5.0",            # NVIDIA GPU monitoring (Windows + Linux)
    # llama-cpp-python and ctransformers added in chunk 3
]
```

`pynvml` is in `ai` extras because it has no useful function without CUDA, and dev machines without GPU shouldn't be forced to install it. The VRAM guard's `_HAS_PYNVML = False` branch keeps the codebase importable without the extra.

`faster-whisper` is in `ai` because of its CTranslate2 dep weight (~200MB).

Both installed via `uv sync --extra ai`. CI's default `uv sync` skips them (already the 2A convention per MEMORY.md); the `test_whisper.py` slow-marked tests are skipped in CI.

---

## 3. Frontend Design

### 3.1 Feature Folder & Shared Kernel Layout

This chunk lives entirely inside the existing `features/import/` folder (extending 2A's library card) plus one new shared-kernel hook.

```
frontend/src/features/import/
├── components/
│   ├── VideoCard/
│   │   ├── index.tsx                    # extended: switches between idle | ProgressOverlay | QueuePositionPill
│   │   ├── ProgressOverlay/index.tsx    # NEW — overlay on thumbnail during transcribing
│   │   ├── QueuePositionPill/index.tsx  # NEW — pill on thumbnail during queued
│   │   └── RetryButton/index.tsx        # NEW — surfaces beside delete IconButton when failed
│   ├── StatusChip/index.tsx             # extended — adds queued/transcribing/ready mappings
│   └── StatusFilterChips/index.tsx      # extended — adds new chips per PRD
├── hooks/
│   ├── useRetryTranscription.ts         # NEW — POST /api/videos/{id}/retry
│   └── useVideos.ts                     # extended — polling now also triggered when any queued/transcribing
└── types.ts                             # regenerated from Pydantic; carries new ProgressEvent, TranscriptDocument

frontend/src/lib/
├── useTranscriptionProgress.ts          # NEW — single WS hook keyed by videoId
├── ws.ts                                # NEW — typed WebSocket client (open, reconnect, dispatch)
└── theme.ts / tokens.ts                 # unchanged (DESIGN.md tokens already cover the new colors)
```

No new pages, no new routes. The transcript GET endpoint exists for 2C — no frontend consumer of it lands in this chunk.

### 3.2 `useTranscriptionProgress` Hook (Shared Kernel)

Lives in `frontend/src/lib/` per chunk plan ("shared kernel: `frontend/src/lib/`").

```ts
type TranscriptionState = {
  status: VideoStatus;
  percent: number;               // 0–100; 0 when status === 'queued'
  stage: 'transcription' | null;
  segmentsDone: number | null;
  segmentsTotal: number | null;
  elapsedSec: number;
  etaSec: number | null;
  queuePosition: number | null;  // 1-indexed; null when not queued
  errorCode: string | null;
  errorMessage: string | null;
  isConnected: boolean;
};

export function useTranscriptionProgress(
  videoId: string,
  options?: { enabled?: boolean }
): TranscriptionState;
```

**Behavior:**
- When `enabled` (default true) AND `videoId` is non-empty, the hook opens a WS to `/ws/{videoId}`.
- On `snapshot` event: replaces local state entirely.
- On `progress` event: merges into local state (percent, ETA, etc.).
- On `complete`: sets `status='ready'`, `percent=100`, `isConnected=false`. Hook does not re-open after `complete`.
- On `error`: sets `status='failed'`, sets `errorCode`/`errorMessage`, `isConnected=false`.
- On WS close (unexpected, not preceded by `complete`/`error`): exponential backoff reconnect — 500ms, 1s, 2s, 5s, capped at 10s. Reconnect re-subscribes and the server's next message is a fresh `snapshot`, so reducer state catches up cleanly without explicit "resync" logic.
- On unmount: closes the WS cleanly.
- On `videoId` change: closes the old WS, opens a new one.

**Implementation skeleton:**

```ts
export function useTranscriptionProgress(videoId, options = {}) {
  const enabled = options.enabled ?? true;
  const [state, setState] = useState<TranscriptionState>(initial);
  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(500);

  useEffect(() => {
    if (!enabled || !videoId) return;

    let cancelled = false;

    function connect() {
      if (cancelled) return;
      const ws = new WebSocket(buildWsUrl(`/ws/${videoId}`));
      wsRef.current = ws;
      ws.onopen = () => {
        backoffRef.current = 500;
        setState(s => ({ ...s, isConnected: true }));
      };
      ws.onmessage = (e) => {
        const event = JSON.parse(e.data) as ProgressEvent;
        setState(s => reduce(s, event));
        if (event.type === 'complete' || event.type === 'error') {
          ws.close();
        }
      };
      ws.onclose = () => {
        if (cancelled) return;
        setState(s => ({ ...s, isConnected: false }));
        // Only reconnect if we did not already see complete/error.
        if (state.status !== 'ready' && state.status !== 'failed') {
          setTimeout(connect, backoffRef.current);
          backoffRef.current = Math.min(backoffRef.current * 2, 10_000);
        }
      };
    }

    connect();
    return () => { cancelled = true; wsRef.current?.close(); };
  }, [videoId, enabled]);

  return state;
}
```

**WS URL derivation (`buildWsUrl`):**

`lib/ws.ts`:

```ts
export function buildWsUrl(path: string): string {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';
  const wsBase = apiBase.replace(/^http/, 'ws');
  return `${wsBase}${path}`;
}
```

(Mirrors `lib/api.ts`'s base-URL convention.)

### 3.3 VideoCard Extension

VideoCard becomes a conditional renderer based on `video.status`:

```tsx
function VideoCard({ video }: { video: VideoDocument }) {
  const isActive = video.status === 'queued' || video.status === 'transcribing';
  const progress = useTranscriptionProgress(video.id, { enabled: isActive });

  return (
    <Card sx={surfaces.mid}>
      <Thumbnail src={video.thumbnailUrl} alt={video.title}>
        {/* Overlay logic */}
        {video.status === 'transcribing' && <ProgressOverlay progress={progress} />}
        {video.status === 'queued' && <QueuePositionPill position={progress.queuePosition} />}
        {video.status === 'ready' && <StatusChip status="ready" />}
        {video.status === 'failed' && <StatusChip status="failed" />}
        {/* Duration mono-pill in bottom-right (2A) — unchanged */}
        <DurationPill seconds={video.durationSec} />
      </Thumbnail>

      <Metadata>
        <Title>{video.title}</Title>
        <Meta>{formatBytes(video.fileSizeBytes)} · {formatRelative(video.createdAt)}</Meta>
        {video.status === 'failed' && (
          <ErrorMessage>{video.errorMessage}</ErrorMessage>
        )}
        <Actions>
          {video.status === 'failed' && <RetryButton videoId={video.id} />}
          <DeleteIconButton videoId={video.id} />
        </Actions>
      </Metadata>

      {/* "Picking up where we left off" hint */}
      {video.restartedAt && Date.now() - new Date(video.restartedAt).getTime() < 30_000 && (
        <ResumptionHint />
      )}
    </Card>
  );
}
```

The hook is only opened (`enabled: true`) when the card is in an active state. Ready/failed cards do not open WS connections — they read static state from `video`. This naturally throttles WS connections to the size of the "currently running or queued" set, which is bounded by the queue + 1.

### 3.4 ProgressOverlay Component

Pure presentational. Receives the live progress state and renders per PRD §UI/UX Direction.

```tsx
function ProgressOverlay({ progress }: { progress: TranscriptionState }) {
  return (
    <Overlay sx={overlayStyles}>      {/* scrim @ 40% per DESIGN.md */}
      <Stack alignItems="center" spacing={0.5}>
        <Typography variant="overline" color="onSurface">TRANSCRIBING</Typography>
        <Typography variant="codeSm" sx={{ fontSize: 24 }}>{progress.percent}%</Typography>
        {progress.etaSec !== null && (
          <Typography variant="body2" color="onSurfaceVariant">
            ~{formatEta(progress.etaSec)} left
          </Typography>
        )}
      </Stack>
      <LinearProgress
        variant="determinate"
        value={progress.percent}
        sx={{
          position: 'absolute', bottom: 0, left: 0, right: 0,
          height: 4,
          bgcolor: 'surfaceContainerHigh',
          '& .MuiLinearProgress-bar': {
            bgcolor: 'primary.main',
            transition: 'transform 600ms cubic-bezier(0.4, 0, 0.2, 1)',
          },
          '@media (prefers-reduced-motion: reduce)': {
            '& .MuiLinearProgress-bar': { transition: 'none' },
          },
        }}
        aria-valuenow={progress.percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Transcribing, ${progress.percent}% complete`}
      />
    </Overlay>
  );
}

function formatEta(sec: number): string {
  if (sec < 60) return `${Math.round(sec)}s`;
  if (sec < 3600) return `${Math.round(sec / 60)} min`;
  return `${(sec / 3600).toFixed(1)} h`;
}
```

All colors from the existing 2A `tokens.ts` — `primary`, `surfaceContainerHigh`, `scrim`, `onSurfaceVariant`. No hex literals.

### 3.5 QueuePositionPill Component

```tsx
function QueuePositionPill({ position }: { position: number | null }) {
  if (position === null) return null;
  const label = position === 1 ? 'NEXT UP' : `${ordinal(position)} IN QUEUE`;
  const isNext = position === 1;
  return (
    <Pill
      sx={{
        position: 'absolute', top: 8, right: 8,
        bgcolor: isNext ? 'tertiaryContainer' : 'surfaceContainerHighest',
        color: isNext ? 'tertiary.main' : 'onSurfaceVariant',
        animation: isNext ? 'pulse 2s ease-in-out infinite' : 'none',
        '@media (prefers-reduced-motion: reduce)': { animation: 'none' },
      }}
    >
      <Typography variant="overline">{label}</Typography>
    </Pill>
  );
}
```

The 2A duration mono-pill swaps to bottom-right when this pill is present (already the spec in PRD).

### 3.6 RetryButton Component

```tsx
function RetryButton({ videoId }: { videoId: string }) {
  const { retry, isLoading } = useRetryTranscription();
  return (
    <Button
      variant="outlined"
      size="small"
      onClick={() => retry(videoId)}
      disabled={isLoading}
      startIcon={<RefreshCw size={16} />}    // Lucide
      sx={{ borderColor: 'primary.main', color: 'primary.main' }}
    >
      Retry
    </Button>
  );
}
```

### 3.7 StatusChip Extension

Adds three new mappings to the 2A `StatusChip` component:

```ts
const STATUS_TOKEN_MAP: Record<VideoStatus, { bg: string; fg: string; label: string }> = {
  uploading:    { bg: 'primaryContainer',   fg: 'primary',   label: 'Uploading' },     // 2A
  imported:     { bg: 'secondaryContainer', fg: 'secondary', label: 'Imported' },      // 2A
  queued:       { bg: 'tertiaryContainer',  fg: 'tertiary',  label: 'Queued' },        // new
  transcribing: { bg: 'primaryContainer',   fg: 'primary',   label: 'Transcribing' },  // new (chip is replaced by overlay in card UI — but used elsewhere)
  ready:        { bg: 'secondaryContainer', fg: 'secondary', label: 'Ready' },         // new
  failed:       { bg: 'errorContainer',     fg: 'error',     label: 'Failed' },        // 2A
};
```

The `transcribing` entry is kept in the map (for use in the `StatusFilterChips` group) even though VideoCard hides the chip during active transcription in favor of the overlay.

### 3.8 StatusFilterChips Extension

The 2A chip group `[All] [Uploading] [Imported] [Failed]` extends to:

`[All] [Importing] [Queued] [Transcribing] [Ready] [Failed]`

Where `[Importing]` is a derived filter: matches `status IN (uploading, imported)`. The frontend translates this to two backend calls (or — simpler — passes a special multi-value query param). Decision: extend the GET endpoint to accept `status=importing` as a virtual value that maps to the two real statuses server-side. This keeps the chip group's URL state simple (`?status=importing`) and the filter chip logic uniform.

Alternative considered: 6-chip group becomes visually heavy. We accept it because the PRD calls for visibility into queue + active states, which are operationally meaningful to the user. If feedback comes back negative we can collapse `[Queued]` + `[Transcribing]` into `[Processing]` in a follow-up.

### 3.9 useRetryTranscription Hook

```ts
export function useRetryTranscription() {
  const { mutate } = useSWRConfig();
  const [isLoading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function retry(videoId: string) {
    setLoading(true);
    setError(null);
    try {
      await api.post(`/api/videos/${videoId}/retry`);
      // Revalidate the videos list to reflect the new status.
      await mutate((key) => Array.isArray(key) && key[0] === 'videos');
    } catch (e) {
      setError(extractMessage(e));
    } finally {
      setLoading(false);
    }
  }

  return { retry, isLoading, error };
}
```

### 3.10 SWR Polling Extension

`useVideos` currently re-polls every 3s when at least one record has `status=uploading` (2A). Extended:

```ts
const refreshInterval =
  hasUploading || hasImported || hasQueued || hasTranscribing ? 3000 : 0;
```

The `hasImported` term is a brief transient (auto-pickup flips imported → queued within 2s of the import write) but covers the window. Once a real WS event triggers a `progress` event for an active video, the WS-driven hook updates UI without waiting for the 3s SWR poll. The poll is the safety net for status transitions that don't traverse the WS (queue position changes, restart sweep effects).

A more efficient future refactor would push status changes via a single video-list WebSocket, but that is out of scope here.

### 3.11 Types & Codegen

The Pydantic-to-TypeScript generator (established in 2A) regenerates `frontend/src/features/import/types.ts` and any new files in the shared kernel.

New types appearing in the generated output:
- `VideoStatus` enum gains three values (`queued`, `transcribing`, `ready`).
- `VideoDocument` gains `lastProgressPercent`, `transcriptionStartedAt`, `transcriptionFinishedAt`, `restartedAt`.
- `TranscriptDocument`, `Segment`, `Word` — new.
- `ProgressEvent` — new (consumed by `useTranscriptionProgress`).

Generated header comment indicates the file is auto-managed.

### 3.12 Design System Conformance

No new tokens. Every color comes from `tokens.ts`. The new motion patterns (progress bar fill transition, status chip cross-fade, hint fade-in/out, pulse) use durations from DESIGN.md defaults or — where DESIGN.md doesn't specify — match similar 2A patterns (180ms, 200ms, 280ms, 600ms). All motion respects `prefers-reduced-motion`.

The no-hex Vitest guard from 2A continues to fail loud on any new hex literal added to the codebase.

---

## 4. Testing Strategy

Test-first per `CLAUDE.md`. First file in each new folder is the test file.

### 4.1 Backend (pytest)

**Fixtures (`tests/conftest.py`):**

- `sample_audio_short` — for non-Whisper tests (coordinator, repository, worker orchestration with `mock_whisper_model`), a 3-second silent MP4 generated via `ffmpeg -f lavfi -i "color=c=black:s=320x240:d=3" -f lavfi -i "anullsrc=r=16000:cl=mono"`. Audio content is irrelevant because Whisper is mocked.
- `recorded_speech_clip` — for the slow-tagged real-Whisper test only, a ~10-second mp4 with a clearly-articulated sentence ("the quick brown fox jumps over the lazy dog") committed at `backend/tests/fixtures/recorded_speech.mp4`. Generated by the implementer during step 13 via `say`/`espeak` + `ffmpeg` (cross-platform path captured in a one-line bash script committed alongside). Ground truth: the sentence text and approximate word boundaries. Not regenerated in CI — the file is checked in.
- `mock_whisper_model` — fixture that replaces `WhisperHandle.model.transcribe` with a deterministic generator yielding a known segment sequence. Used in all non-slow tests.
- `fake_pynvml` — fixture that patches `pynvml.nvmlDeviceGetMemoryInfo` to return a configurable `(free_bytes, used_bytes, total_bytes)`. Used to test VRAM guard pass/fail branches.
- `test_db_with_video` — convenience fixture that inserts a video record at a given status, returns its id.
- `ws_client` — `httpx_ws.aconnect_ws(...)` against the test app, used in WS integration tests.

**Test files map to acceptance criteria:**

| Test | AC covered |
|---|---|
| `test_enqueue_flips_imported_to_queued` | Story 1 |
| `test_enqueue_idempotent_when_already_queued` | Story 1 |
| `test_worker_processes_queued_in_fifo_order` | Story 3 |
| `test_worker_skips_when_queue_empty` | (worker idle behavior) |
| `test_worker_advances_after_failure` | Story 4 |
| `test_progress_events_throttled_to_one_per_second` | Story 2 (latency) |
| `test_snapshot_returned_to_new_subscriber` | Story 2 (reconnect / page reload) |
| `test_snapshot_on_terminal_video_sends_complete_and_closes` | Story 2 (subscribe-after-finish) |
| `test_ws_invalid_video_id_sends_error_and_closes` | (defensive) |
| `test_count_queued_before_returns_zero_indexed_position` | Story 3 (position computation) |
| `test_sweep_returns_transcribing_to_queued_and_sets_restartedAt` | Story 5 |
| `test_backfill_imported_to_queued_on_startup` | Story 5 (post-deploy back-fill) |
| `test_vram_guard_passes_when_budget_available` | Story 6 |
| `test_vram_guard_fails_with_VRAMUnavailable_when_below_budget` | Story 6 |
| `test_vram_guard_no_op_when_skip_flag_set` | (test-only escape valve) |
| `test_retry_endpoint_flips_failed_to_queued_and_clears_error` | Story 4 |
| `test_retry_endpoint_returns_200_on_already_queued` | Story 4 (idempotency) |
| `test_retry_endpoint_returns_409_on_uploading_video` | Story 4 (invalid transition) |
| `test_transcript_get_returns_404_when_no_transcript_yet` | (2C contract) |
| `test_transcript_get_returns_document_when_ready` | (2C contract) |
| `test_transcription_timeout_marks_failed_after_4x_duration` | (timeout guard) |
| `test_video_delete_during_active_transcription_cleanly_cancels` | (delete-cascade interaction) |

**Slow tests (`@pytest.mark.slow`, skipped in default CI run):**

- `test_whisper_transcribes_known_audio_within_tolerance` — Real Whisper run against a known 10-second fixture (single sentence). Asserts: detected text contains the expected word, per-word timestamps within ±100ms of ground truth, throughput ≥50 words/min (extrapolated). Requires the model file present.
- `test_full_pipeline_imported_to_ready` — End-to-end: insert a video record at `imported`, let the worker pick it up, assert it reaches `ready` with a non-empty transcript. Requires the model file.

Slow tests run on demand: `uv run pytest -m slow` (after `uv sync --extra ai` and Whisper download).

**Coverage target:** 90%+ on `coordinator.py`, `service.py`, `repository.py` extensions, `core/ws/manager.py`, `core/gpu/vram.py`, `workers/transcription.py`. No coverage gate on `whisper.py` (the real model integration) — exercised by slow tests only.

### 4.2 Frontend (Vitest)

**Unit tests:**

- `lib/useTranscriptionProgress.test.ts`:
  - Opens WS to correct URL when `enabled=true` and `videoId` non-empty.
  - Does not open WS when `enabled=false`.
  - `snapshot` event replaces state.
  - `progress` event merges into state.
  - `complete` event sets status=ready, percent=100, closes WS.
  - `error` event sets errorCode/errorMessage, closes WS.
  - Unexpected close triggers reconnect with backoff sequence (500/1000/2000/5000/10000, capped).
  - Cleanly closes on unmount.
  - Re-opens on `videoId` prop change.
  - Mocks: `globalThis.WebSocket` replaced with a controllable fake that exposes `triggerOpen`/`triggerMessage`/`triggerClose`.
- `features/import/components/VideoCard/ProgressOverlay.test.tsx`:
  - Renders percent, stage label, ETA from props.
  - `aria-valuenow` matches percent.
  - LinearProgress bar receives correct value.
  - ETA hidden when null.
  - Reduced-motion disables the transition (asserted via CSS-in-JS query).
- `features/import/components/VideoCard/QueuePositionPill.test.tsx`:
  - Position 1 → "NEXT UP" with tertiary color.
  - Position 5 → "5TH IN QUEUE".
  - Null position → nothing rendered.
  - Pulse animation disabled under reduced motion.
- `features/import/components/VideoCard/RetryButton.test.tsx`:
  - Click calls `retry(videoId)`.
  - Disabled while loading.
- `features/import/components/VideoCard/VideoCard.test.tsx`:
  - `status=transcribing` renders ProgressOverlay (not StatusChip).
  - `status=queued` renders QueuePositionPill (not StatusChip).
  - `status=failed` renders RetryButton + ErrorMessage + DeleteIconButton.
  - `status=ready` renders StatusChip("ready").
  - `restartedAt` within last 30s renders ResumptionHint; older → not rendered.
- `features/import/hooks/useRetryTranscription.test.ts`:
  - POST hits correct endpoint.
  - Triggers SWR `mutate` on success.
  - Sets error on failure.

**Design conformance (extends 2A's tests):**
- The existing `no-hex.test.ts` guard automatically catches any new hex literal introduced by this chunk.
- `StatusChip.test.tsx` extended to cover the three new statuses against their DESIGN.md token mappings.

**E2E (Playwright):**
- `e2e/transcription-pipeline.spec.ts`:
  - Upload a fixture video → card transitions imported → queued → transcribing within a bounded wait. (Uses the mocked Whisper backend for speed — real Whisper E2E is too slow for CI.)
  - Progress bar advances during transcribing state.
  - Card flips to `ready` and StatusChip becomes "Ready".
  - Refresh browser mid-transcription → bar resumes at >= previously-observed percent (within 1s of load).
  - Force-fail (via test endpoint that injects a fake failure) → card shows error + RetryButton. Click Retry → status returns to `queued`.

The Playwright spec is authored but, like 2A's, may be user-run only (boots a 2-server stack with a special test fixture for the mocked Whisper).

### 4.3 Test Doubles for Whisper

Two layers of doubling, used at different test scopes:

1. **`mock_whisper_model` fixture (unit-test scope):** Replaces `WhisperHandle.model.transcribe` with a generator that yields a configurable number of segments with synthetic timestamps and text. Used in `test_coordinator.py`, `test_worker.py`, and any test that needs to observe the orchestration around Whisper without paying the load cost.
2. **Real Whisper (slow-test scope):** Loads the actual model from `models/whisper-medium`. Used in `test_whisper.py` slow tests for transcript-accuracy assertions.

CI defaults to the unit scope (no `--extra ai` install needed). Slow tests are an opt-in local run before tagging a release of this chunk.

---

## 5. File System Layout (Runtime)

```
media/
├── originals/                  # unchanged from 2A
├── thumbnails/                 # unchanged from 2A
└── logs/                       # JSON logs; new events listed in §2.13

models/
└── whisper-medium/             # downloaded by scripts/download_models.py (Phase 1)
    ├── model.bin
    ├── tokenizer.json
    └── ...                     # CTranslate2 model files
```

No new disk locations are introduced. Transcripts live in MongoDB.

---

## 6. Migration from 2A

| Item | Action |
|---|---|
| `videos` collection | Add `{status: 1, transcriptionStartedAt: 1}` index in `scripts/init_db.py`. Schema gains new optional fields (no data migration needed). |
| `transcripts` collection | New. Created lazily on first insert; index `{videoId: 1}` unique added in `init_db.py`. |
| `VideoStatus` enum | Move from `features/import/schemas.py` to `app/core/schemas/video_status.py`. Update 2A's import to point at new location. Tests in 2A continue to pass without behavioral change. |
| `features/import/service.py` | Add `await enqueue(video.id)` after successful import insert (upload path AND yt-dlp post-download). |
| `features/import/tasks.py` | Same addition in `download_youtube`. |
| `app/main.py` | Remove placeholder WS handler; include `core/ws/routes.router`. Include `features/transcription/routes.router`. Lifespan starts the worker task and runs `back_fill_at_startup()` after the existing 2A startup sweep. |
| `app/core/config.py` | Add six new fields (§2.12). Update `.env.example`. |
| `app/core/models/loader.py` | Replace `load_whisper_medium` stub with the real implementation (§2.4). |
| `backend/pyproject.toml` | Add `faster-whisper` and `pynvml` to `ai` extras. |
| `scripts/init_db.py` | Add transcripts collection, two new indexes. Idempotent. |
| `frontend/src/lib/useTranscriptionProgress.ts` | New. |
| `frontend/src/lib/ws.ts` | New. |
| `frontend/src/features/import/components/VideoCard/index.tsx` | Extend to render new overlays. |
| `frontend/src/features/import/components/VideoCard/{ProgressOverlay,QueuePositionPill,RetryButton}/` | New. |
| `frontend/src/features/import/components/StatusChip/index.tsx` | Extend status token map. |
| `frontend/src/features/import/components/StatusFilterChips/index.tsx` | Extend chip group + `importing` virtual filter. |
| `frontend/src/features/import/hooks/useRetryTranscription.ts` | New. |
| `frontend/src/features/import/hooks/useVideos.ts` | Extend polling condition. |
| `frontend/src/features/import/types.ts` | Regenerated from updated Pydantic schemas. |

---

## 7. Technical Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `asyncio.run_coroutine_threadsafe(...).result()` blocking the Whisper worker thread on slow WS broadcast | Med | Med | WS broadcasts are tiny payloads to local subscribers — sub-millisecond. Worst case a slow subscriber drops; broadcast continues. Throttling caps per-video broadcast volume. |
| `faster-whisper`'s segment iterator releases GIL erratically, starving the asyncio loop | Low | Med | `asyncio.to_thread` runs in a real thread pool; the main loop is independent. Tested in `test_progress_events_throttled` which verifies WS events flow during a mocked transcribe. |
| Mongo `find_one_and_update` race when worker + sweep both run concurrently | Low | High | Atomic operator at the DB level; both paths use `{status: queued}` precondition. The sweep is one-shot at lifespan startup (before the worker task starts) per the lifespan ordering in `app/main.py`. |
| pynvml absent on dev machine, breaks `uv sync` (no ai extras) | Low | Low | `_HAS_PYNVML` import-guarded; the guard module imports cleanly without pynvml. Tests for the guard cover both branches. |
| `pydantic-to-typescript` emits unusable types for `Literal[...]` discriminated unions | Med | Med | `ProgressEvent.type` is `Literal["snapshot", "progress", "complete", "error"]`. If codegen produces `string` instead of the union, fall back to hand-written narrowing on the consumer side. Smoke test in `test_generate_ts` verifies the union is preserved. |
| WS subscriber count grows unboundedly if cards never unmount | Low | Low | The hook is `enabled=true` only for `queued`/`transcribing` cards. Cards in other states do not open WS. The library page can show at most queue-length + 1 active WS connections — small bounded number. |
| 2A test environment hits `enqueue` on every imported video and unexpectedly cascades into a worker run | Low | Med | The worker task is NOT started in `app_client` test fixture (tests instantiate the FastAPI app without the lifespan worker hook). Coordinator tests exercise enqueue directly. |
| `transcript_finished_at - transcription_started_at` is the wrong elapsed for ETA after restart | Med | Low | ETA is recomputed from job-local elapsed (worker tracks `time.monotonic()` at the start of the `transcribe()` call), not from DB timestamps. After restart, elapsed resets to 0 — ETA briefly shows "—" until first segment completes. Acceptable. |
| Whisper model load on first job blocks the worker loop for ~5 seconds; user sees "queued" without movement | Med | Low | Add a `loading_model` WS event between `snapshot` (queued) and the first `progress` to signal "we're warming up" — emitted from the worker just before the model load. Optional; can ship without and revisit if user feedback shows confusion. |
| Mongo 16MB BSON limit on transcript document for 4-hour video | Low | High | Worst-case estimate ~12MB (PRD §Risk). If a future test reproduces an exceeding case, split into segments-per-chunk subdocuments. Not implemented in 2B. |

---

## 8. Implementation Order (TDD-Friendly)

Each step delivers one tested unit. No step depends on later steps for correctness. Atomic commits per step, Conventional Commits.

1. **Shared kernel: VideoStatus relocation.** Move `VideoStatus` from `features/import/schemas.py` to `app/core/schemas/video_status.py`. Update 2A's import. Tests: existing 2A tests pass; new enum values not yet added (added in step 4).
2. **Shared kernel: VRAM guard.** `app/core/gpu/vram.py` + `test_vram.py` with mocked pynvml. Tests cover: pass when free ≥ budget+margin, raise `VRAMUnavailableError` otherwise, no-op when `skip_vram_guard=True`, graceful handling when pynvml unavailable.
3. **Shared kernel: WS manager.** `app/core/ws/manager.py` + `test_manager.py`. Tests: subscribe/disconnect, broadcast to multiple subscribers, broadcast to no subscribers is a no-op, individual subscriber failure doesn't block others.
4. **Backend: schemas.** Extend `VideoStatus` enum (3 new values). Add `TranscriptDocument`, `Segment`, `Word`, `ProgressEvent`, `RetryResponse` to `features/transcription/schemas.py`. Tests: Pydantic round-trip with camelCase aliases, discriminator handling on `ProgressEvent.type`.
5. **Backend: errors.** `features/transcription/errors.py` with the catalog. Tests: domain exceptions carry the right code, HTTP mapping is correct.
6. **Backend: config extensions.** Six new fields in `core/config.py`. Tests: env override parses correctly for each. Update `.env.example`.
7. **Backend: transcript repository.** `features/transcription/repository.py` + `test_repository.py`. Tests against test DB: insert/get/delete, unique-index enforcement on `videoId`.
8. **Backend: video repository extensions.** Add `claim_next_queued`, `transition_status`, `update_progress`, `sweep_stale_transcribing`, `back_fill_imported`, `count_queued_before` to the existing `VideoRepository`. Tests against test DB for each.
9. **Backend: coordinator.** `features/transcription/coordinator.py` + `test_coordinator.py`. Tests: `enqueue` happy + idempotent paths; `retry` happy + invalid-transition; `back_fill_at_startup` sweeps and back-fills correctly.
10. **Backend: db init script update.** `scripts/init_db.py` adds transcripts collection + two new indexes. Test: re-run is idempotent; indexes appear in `index_information()`.
11. **Backend: WS endpoint.** `app/core/ws/routes.py` + tests. Tests: connection lifecycle (accept, snapshot, hold, disconnect), invalid videoId → error + close, terminal state → complete/error + close.
12. **Backend: model loader wiring.** Replace `load_whisper_medium` stub with real `faster_whisper.WhisperModel(...)`. Add VRAM-guard call before construction. Test: covered indirectly by slow tests in step 13; unit test asserts VRAM guard is invoked (mocked).
13. **Backend: Whisper service.** `features/transcription/whisper.py` with the `WhisperService.transcribe(on_segment)` pattern. Unit tests use `mock_whisper_model` to verify orchestration. Slow test (`@pytest.mark.slow`) verifies real transcription against fixture audio.
14. **Backend: worker loop.** `workers/transcription.py` with the run-forever pattern. Tests: claims queued videos in FIFO order, advances on failure, sleeps when empty, throttles progress broadcasts, handles VRAMUnavailable + timeout + AudioDecode failures.
15. **Backend: transcription service + routes.** `features/transcription/service.py` (get_transcript, retry) and `routes.py` (POST /retry, GET /transcript). Tests: HTTP integration for each.
16. **Backend: integrate enqueue into 2A.** Add `await enqueue(video_id)` to 2A's import service in two places. Test: importing a video flips it to `queued` within the same test (worker not started — coordinator runs in-line).
17. **Backend: lifespan wiring.** Replace placeholder WS in `app/main.py`. Include new routers. Start worker task in lifespan. Run `back_fill_at_startup` before worker starts. Tests: lifespan smoke test.
18. **Backend: TS codegen.** Regenerate `frontend/src/features/import/types.ts`. Verify `ProgressEvent` discriminator is preserved (smoke test in `test_generate_ts`).
19. **Frontend: WS client utility.** `lib/ws.ts` + `lib/ws.test.ts`. Tests: URL derivation, reconnect logic.
20. **Frontend: useTranscriptionProgress hook.** `lib/useTranscriptionProgress.ts` + tests. Mocked WebSocket; verifies all five behaviors (snapshot, progress, complete, error, reconnect-backoff).
21. **Frontend: useRetryTranscription hook.** `features/import/hooks/useRetryTranscription.ts` + tests.
22. **Frontend: ProgressOverlay component.** `features/import/components/VideoCard/ProgressOverlay/` + tests.
23. **Frontend: QueuePositionPill component.** + tests.
24. **Frontend: RetryButton component.** + tests.
25. **Frontend: ResumptionHint component.** + tests.
26. **Frontend: VideoCard extension.** Wire all new sub-components conditionally on `video.status`. Update tests in `VideoCard.test.tsx`.
27. **Frontend: StatusChip extension.** Add new status mappings. Tests verify each.
28. **Frontend: StatusFilterChips extension.** Add new chips; wire `importing` virtual filter (server-side mapping). Tests verify filter behavior.
29. **Frontend: useVideos polling extension.** Update polling condition. Tests verify polling toggles correctly.
30. **Frontend: E2E.** `e2e/transcription-pipeline.spec.ts`.
31. **Verification report.** AC-to-test matrix at `docs/features/transcription-pipeline/transcription-pipeline-verification.md`.

Atomic commits per step. Step numbers map to Conventional Commit subjects: `feat(transcription): add VRAM guard`, `feat(transcription): wire worker loop`, etc.

---

## 9. Open Questions for Tech Lead Review

**Q1: `/ws/{video_id}` vs `/ws/{job_id}`.**
The PRD and chunk plan refer to "jobs" and the placeholder uses `/ws/{job_id}`. This chunk uses `/ws/{video_id}` because 2B has exactly one job per video (one stage = transcription = atomic) and introducing a separate `jobs` collection adds writes + tests with no immediate user-visible benefit. Phase 3 will need real jobs (Llama analysis = a second stage on the same video, plus restart-attempts auditing). When that happens, we introduce a `jobs` collection and the WS path becomes `/ws/{job_id}` — `video_id` remains valid as a query-param alias for backwards compatibility, or we route both paths to the same handler. **Tech Lead: confirm this deferred-jobs approach, or push back and we introduce a lightweight jobs collection now.**

**Q2: Whisper segment-iterator threading vs subprocess.**
We run `model.transcribe()` in `asyncio.to_thread` and bridge segment callbacks via `run_coroutine_threadsafe`. The alternative is spawning a subprocess per transcription that streams segments back over stdout/IPC. Subprocess gives crash isolation (segfault doesn't kill uvicorn) but adds: model load per process (~5s startup × every job — destroys our "stay loaded" cost amortization), IPC complexity, and a second runtime to instrument. We chose threading. **Tech Lead: confirm. The "keep model loaded" cost-saver is the dominant factor.**

**Q3: 6-chip filter group.**
PRD calls for `[All] [Importing] [Queued] [Transcribing] [Ready] [Failed]`. Six chips is visually heavy. Alternatives: collapse `[Queued] + [Transcribing]` into `[Processing]` (5 chips) or `[Importing] + [Queued] + [Transcribing]` into `[In Progress]` (4 chips). The 6-chip version is operationally explicit and matches each status 1:1; the collapsed versions are visually cleaner but hide information. **Tech Lead: pick a variant or defer the question to a UX revisit after the rest of 2B is in.**

**Q4: `loading_model` WS event.**
First-job model load takes ~5 seconds during which the user sees `queued` not moving. We can emit a `loading_model` event after the worker claims the video but before the first `progress`, so the UI can show "Loading model…" instead of a static queued state. Adds: one more event type to `ProgressEvent.type`, one more reducer branch in `useTranscriptionProgress`, minor UI polish. We've left this out of the v1 ship list — would be a small follow-up commit if you want it in. **Tech Lead: include now or defer?**

**Q5: ETA on a restarted job.**
After a backend restart that auto-requeues a job, the worker's monotonic clock for that job starts fresh. ETA briefly shows "—" until the first segment completes — then linear extrapolation kicks in. We could persist `transcriptionStartedAt` and compute ETA off DB elapsed instead, but that double-counts the time-during-which-the-process-was-dead. Current behavior: small visible glitch on the first 5–10 seconds post-restart. **Tech Lead: confirm acceptable, or want job-clock persistence?**

**Q6: Transcript GET in 2B vs 2C.**
We ship the GET endpoint here so 2C is purely frontend. Alternative is to defer the endpoint to 2C and ship 2B as a pure pipeline+UX update. We include it because: (a) it lets the verification test #12 prove forward-compat, (b) it's ~30 lines of route + repository, and (c) it keeps 2C scope to UI only. **Tech Lead: confirm or push back.**

---

## 10. Definition of Done

This document is implemented when:

- All 31 implementation steps complete with passing tests.
- `cd backend && uv run pytest -m "not slow"` green, with 90%+ coverage on the modules listed in §4.1.
- `cd backend && uv run pytest -m slow` green on a workstation with Whisper medium installed and the GPU available — verifies the real-model integration. (Not gated in CI.)
- `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app/` green.
- `cd frontend && pnpm lint && pnpm vitest run && pnpm build` green.
- No-hex Vitest guard from 2A still green (no new hex literals introduced).
- Playwright E2E (`e2e/transcription-pipeline.spec.ts`) green when manually run against the local stack.
- All 12 verification scenarios from the PRD pass — including the explicit `taskkill` mid-transcription scenario and the manual `nvidia-smi` VRAM check.
- Verification Report committed to `docs/features/transcription-pipeline/transcription-pipeline-verification.md` mapping every AC to its test(s).
- User approves Gate 3.
