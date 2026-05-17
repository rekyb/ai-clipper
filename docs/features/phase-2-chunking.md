# Phase 2 — Chunking Plan

Phase 2 of the execution plan (`docs/execution-plan.html`) is split into 3 chunks.
Each chunk is a self-contained feature that goes through the full gated workflow
(PRD → Tech Docs → Implementation → Verification) defined in `CLAUDE.md`.

Each chunk should be implemented in its own session. Start a session by reading
this file, then read `CLAUDE.md`, then read the relevant section of
`docs/execution-plan.html` (Phase 2, lines ~205-297), then invoke
`/product-requirements` to draft the chunk's PRD.

---

## Chunk 2A — Video Import Foundation

**Folder:** `docs/features/video-import/`
**Est:** ~1 day
**Branch:** `feat/video-import`

### In scope

- Backend
  - `POST /api/videos/upload` — multipart file upload
  - `POST /api/videos/download-url` — URL download via yt-dlp
  - Format validation (MP4, MKV, AVI, MOV, WebM) via ffprobe
  - Thumbnail extraction + duration parsing
  - Persist video metadata to MongoDB `videos` collection
  - Feature folder: `backend/app/features/import/`
- Frontend
  - Drag-and-drop upload + file picker + URL input
  - Basic video library list page (cards with thumbnail, title, duration)
  - Feature folder: `frontend/src/features/import/`

### Out of scope (deferred to 2B/2C)

- Transcription (no Whisper integration yet)
- WebSocket / real-time progress
- Transcript display

### Demo / Verification

- Upload an MP4 → record appears in `videos` collection with status `imported`
- Submit a YouTube URL → yt-dlp downloads → same flow
- Library page lists uploaded videos with thumbnails

---

## Chunk 2B — Transcription Pipeline + WebSocket Progress

**Folder:** `docs/features/transcription-pipeline/`
**Est:** ~1.5 days
**Branch:** `feat/transcription-pipeline`
**Depends on:** Chunk 2A merged

### In scope

- Backend
  - faster-whisper service wrapping Whisper medium (CTranslate2, float16)
  - Word-level timestamps + confidence output
  - Job manager (status tracking, idempotent resumption per `CLAUDE.md`)
  - Pipeline coordinator: import → transcription handoff
  - VRAM guard via pynvml (assert free VRAM before model load — hard lock)
  - WebSocket endpoint `/ws/{job_id}` + connection manager
  - Message types: `transcription_progress`, `error`, `complete`
  - Persist transcript to MongoDB (per-stage checkpoint for resumption)
- Frontend
  - `useTranscriptionProgress` hook (shared kernel: `frontend/src/lib/`)
  - Progress bar with percentage + stage label + ETA
  - Status badge on video card (importing → transcribing → ready)

### Out of scope (deferred to 2C)

- Transcript viewer UI
- Click-to-seek

### Demo / Verification

- Upload video → progress streams live via WebSocket
- Transcript saved to DB with word timestamps + confidence
- Timestamps accurate within ±100ms, throughput ≥50 words/min of video
- VRAM stays within budget (≤7.0GB allocated, verified via nvidia-smi)
- Job survives a backend restart and resumes from last completed stage

---

## Chunk 2C — Transcript Viewer

**Folder:** `docs/features/transcript-viewer/`
**Est:** ~0.5 day
**Branch:** `feat/transcript-viewer`
**Depends on:** Chunk 2B merged

### In scope

- Frontend
  - `TranscriptView` component (`frontend/src/features/import/`)
  - Word-level rendering with timestamps
  - Confidence color-coding (heatmap: red <0.5, yellow 0.5-0.8, green ≥0.8)
  - Click-to-seek stub (emits seek event; actual player wiring in Phase 3)
  - Video detail page route: `/video/[id]`

### Out of scope

- Video player (Phase 3)
- Clip browser (Phase 3)
- Inline editing of transcript

### Demo / Verification

- Open `/video/[id]` → scrollable transcript renders
- Confidence heatmap visible per word
- Click word → seek event fires (verified via test stub or console log)

---

## Shared notes for all chunks

- Follow TDD per `CLAUDE.md` — test file is the first file created in each feature folder
- Generate TypeScript types from Pydantic models via `pydantic-to-typescript` after any schema change — never hand-mirror
- Append a session entry to `docs/memory.md` at end of each chunk (newest-first)
- Conventional Commits, atomic commits, branch per chunk
