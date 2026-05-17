# Product Requirements Document: Transcription Pipeline + WebSocket Progress

**Feature:** Transcription Pipeline (Phase 2, Chunk 2B)
**Version:** 1.0
**Date:** 2026-05-17
**Author:** Sarah (Product Owner)
**Quality Score:** 95/100
**Design System:** Conforms to `DESIGN.md` (Vivid Velocity) at the project root. No new visual style introduced.
**Depends on:** Chunk 2A (Video Import Foundation) — merged

---

## Executive Summary

Chunk 2B turns the imported videos from 2A into something the rest of the pipeline can reason about: a word-accurate transcript with timestamps and confidence scores. The moment a video lands in the library, the system automatically begins transcribing it with Whisper medium, and the user sees the progress stream live on the video card — percent complete, current stage label, and a running ETA.

Multiple uploads queue cleanly behind one another (single GPU, sequential FIFO), the queue position is visible per card, and if the backend dies mid-job it picks up where it left off the moment uvicorn restarts. When transcription succeeds the card flips to a "Ready" badge and the transcript is persisted for Chunk 2C (transcript viewer) to render.

This chunk does NOT ship a transcript viewer UI — that is 2C's scope. It DOES ship the data, the live progress feedback, and the operational story (queue, restart-safety, VRAM guard, retry on failure) that makes the rest of Phase 2 viable.

---

## Problem Statement

**Current Situation:** Videos can be imported into the library (Chunk 2A) but nothing happens after that. The pipeline cannot identify viral candidates because there is no transcript to analyze. Phase 3 (clip selection, scoring, export) has no input.

**Proposed Solution:** A transcription pipeline that auto-starts when a video is imported, runs Whisper medium with word-level timestamps and confidence, streams real-time progress to the user via WebSocket, and persists the result to the database. Multiple uploads queue behind one another in FIFO order on the single GPU. The pipeline survives backend restarts.

**Business Impact:** Unblocks all downstream analysis. Establishes the long-running-job, real-time-progress, and GPU-resource-governance patterns that Stages 2 (Llama analysis) and 3 (export) will reuse. Validates the WebSocket contract end-to-end under realistic load (transcribing a 30-minute video takes 5–10 minutes — long enough to exercise reconnect, snapshot, and ETA logic against real data, not a stub).

---

## Success Metrics

**Primary KPIs:**
- **Transcription throughput:** ≥50 words per minute of source video, sustained over a 30-minute clip (per execution-plan §2.4 verification).
- **Timestamp accuracy:** Per-word `start` and `end` timestamps within ±100ms of the underlying audio (per execution-plan §2.4 verification).
- **VRAM safety:** GPU memory allocation never exceeds 7.0 GB during transcription (per `CLAUDE.md` hard lock). Verifiable via `nvidia-smi` during a live job.
- **Restart resilience:** A video in `transcribing` state when the backend is killed returns to a usable state (running or queued) within 10 seconds of the next backend start, with no manual intervention.
- **Progress latency:** Frontend progress bar updates within 1 second of backend Whisper segment completion (excluding network round-trip).

**Validation:** Verified during Gate 3 with a representative sample (3 short videos < 5 min, 1 medium video ~30 min, 1 long video ~90 min if hardware permits) plus a deliberate `taskkill` mid-transcription to exercise restart sweep.

---

## User Personas

### Primary: Solo Content Creator

Same persona as 2A (single-user, local-first, intermediate technical). The new 2B-relevant behaviors:

- **Goals (this chunk):** Drop a video and walk away. Come back to a transcribed library, ready for clipping. Have confidence the GPU isn't being abused or the queue isn't stuck.
- **Pain Points:** Online transcription services charge per minute and are slow; running Whisper from a CLI loses progress visibility; jobs that silently fail mid-run waste hours of wall-clock.

No additional personas.

---

## User Stories & Acceptance Criteria

### Story 1: Transcription starts automatically after import

**As a** solo content creator
**I want** transcription to begin the moment a video finishes importing
**So that** I don't have to babysit the library or click "Transcribe" on every video

**Acceptance Criteria:**
- [ ] Within 2 seconds of a video reaching status `imported`, the system transitions it to `queued` (or `transcribing` if no other job is in flight).
- [ ] The user takes no action between upload completion and transcription starting — no buttons, no prompts.
- [ ] Both file-upload imports and YouTube URL imports trigger transcription identically.
- [ ] Videos imported by 2A before this chunk shipped (status `imported`) are picked up by the queue on the first backend boot after deploy — no manual SQL/Mongo edit required.

### Story 2: See live progress while transcription runs

**As a** solo content creator
**I want** to watch transcription progress in real time on the video card
**So that** I know the system is working and roughly how long it will take

**Acceptance Criteria:**
- [ ] The video card surfaces a progress bar overlaid on (or below) the thumbnail while status is `transcribing`.
- [ ] The progress bar shows: percent complete (0–100), the current stage label ("Transcribing"), and an estimated time remaining ("~3 min left").
- [ ] Progress updates appear within 1 second of backend movement (no manual refresh needed).
- [ ] On page reload mid-transcription, the bar resumes at the correct position within 1 second of page load (no jump from 0).
- [ ] If the user navigates to another route and back, the bar continues to show live progress on return (no need to re-trigger the connection manually).
- [ ] If the browser tab loses network briefly and reconnects, the bar snaps to current progress (no replay of historical events, no stuck-at-old-value).

### Story 3: Multiple videos queue cleanly

**As a** solo content creator
**I want** to upload several videos in a row and have them transcribe one after another
**So that** I can batch-import and walk away

**Acceptance Criteria:**
- [ ] When a transcription is already in flight, the next imported video shows status `queued` on its card.
- [ ] Queued cards display their position in the queue ("2nd in queue", "3rd in queue", etc.). The currently-transcribing video does not show a queue position.
- [ ] When the current transcription completes, the next queued video transitions to `transcribing` within 2 seconds and the remaining queue positions decrement.
- [ ] Queue order is strict FIFO by import-completion time.
- [ ] The queue is persisted in the database — restarting the backend does not lose queued videos or shuffle their order.

### Story 4: Failed transcriptions are surfaced and retryable

**As a** solo content creator
**I want** failed transcriptions to show me what went wrong and let me retry
**So that** a transient error (driver hiccup, corrupt frame, etc.) doesn't leave my library stuck

**Acceptance Criteria:**
- [ ] If transcription fails terminally (Whisper raises a non-recoverable error, audio cannot be decoded, etc.), the card flips to status `failed` with a human-readable error message visible on the card.
- [ ] A `Retry` button appears on the card while status is `failed`. Clicking it returns the video to `queued`, clearing the previous error.
- [ ] The error is also recorded with a machine-readable code (`TRANSCRIPTION_FAILED`, `VRAM_UNAVAILABLE`, `AUDIO_DECODE_FAILED`, etc.) for diagnostics.
- [ ] Failures do not block the queue — the next queued video begins as soon as the failed one is marked terminal.

### Story 5: Transcription survives a backend restart

**As a** solo content creator
**I want** the system to pick up where it left off if I restart the backend (or it crashes)
**So that** a 30-minute transcription isn't lost because I rebooted my laptop

**Acceptance Criteria:**
- [ ] If the backend is killed (any cause) while a video is `transcribing`, the next backend boot returns that video to `queued` automatically — within 10 seconds of the lifespan startup.
- [ ] The user sees the card briefly show a "Picking up where we left off…" message or equivalent feedback (the previous `lastProgressPercent` is preserved on the record and surfaced) so the restart isn't invisible.
- [ ] No data loss: the video record, source file, and queue order are all intact across the restart.
- [ ] If the same video crashes the backend twice in a row, it should still recover (no special poison-pill detection in this chunk — restart-loop hardening is deferred).

### Story 6: GPU is never over-committed

**As a** solo content creator
**I want** to trust that the transcription pipeline will not crash my desktop or stall my GPU
**So that** I can keep using my machine for other work while jobs run in the background

**Acceptance Criteria:**
- [ ] Before each model load, the system asserts that at least the configured VRAM budget is available on the GPU. If not, the job fails fast with `VRAM_UNAVAILABLE` rather than attempting the load and crashing the driver.
- [ ] Total GPU memory allocation by this chunk never exceeds 7.0 GB during steady-state transcription (verifiable via `nvidia-smi`).
- [ ] On `VRAM_UNAVAILABLE`, the video is marked `failed` with that code so the user can free other GPU consumers (close a game, kill another model) and click Retry.

---

## Functional Requirements

### Core Features

**Feature 1: Auto-triggered Transcription**
- The moment a video reaches `imported` (from 2A), the pipeline coordinator picks it up.
- If no transcription is in flight, the video transitions directly to `transcribing`.
- If a transcription is in flight, the video transitions to `queued` and joins the FIFO tail.
- A backend restart sweep on lifespan startup picks up any `imported` records (including those from before 2B shipped) plus any records left in `transcribing` by a previous-process crash, returning them to `queued`.

**Feature 2: Word-Level Transcript with Confidence**
- The transcript output is organized as ordered segments, each containing ordered words.
- Each word carries: the word text, start timestamp, end timestamp, and confidence score (0.0–1.0).
- Each segment carries: aggregated start/end, the full segment text, and diagnostic signals (average log-probability, no-speech probability) for future debugging UI.
- The full transcript is persisted to the database in a single atomic write after Whisper completes successfully. Partial transcripts are not persisted (stage-level atomic per the chunk plan).
- Transcript language is auto-detected by Whisper and recorded on the document.

**Feature 3: Live WebSocket Progress**
- While a video is `queued` or `transcribing`, the user sees live progress on its card in the library, updating in real time without manual refresh.
- A WebSocket channel surfaces per-job progress events: current percent (0–100), stage label, segments completed, total segments, elapsed seconds, ETA seconds.
- On (re)opening the channel, the user immediately receives a snapshot of the current state — there is no replay of historical events and no visible "starting from 0%" jump after a refresh or reconnect.
- On terminal state (`ready`, `failed`), the user receives a final event identifying the outcome and the channel closes.
- The exact message envelope and connection lifecycle are defined in the Gate 2 Tech Doc.

**Feature 4: FIFO Queue with Visible Position**
- Queued videos display their position in the queue on the card ("2nd in queue", "3rd in queue").
- Position is derived (1-indexed by `createdAt` among `queued` videos) — not stored as a mutable field — so insertion/removal doesn't require re-numbering.
- The currently-transcribing video does not show a queue position (it is at position 0 implicitly).
- Queue order survives backend restart because it is derived from `createdAt`, which is set at import time.

**Feature 5: Retry on Failure**
- A `Retry` action is exposed on cards in status `failed`. The action returns the video to `queued`, clears the previous error code/message, and (if no transcription is in flight) the worker picks it up immediately.
- Retry is rate-limited only by the user's clicks — there is no automatic retry-with-backoff in this chunk (deferred to a later operational pass).
- Retry endpoint is idempotent: clicking Retry on a video already in `queued`/`transcribing` is a no-op that returns 200.

**Feature 6: VRAM Guard (Hard Lock)**
- Before loading the Whisper model for the first job (and before any reload), the pipeline queries the GPU's available VRAM.
- If the available VRAM is below the configured budget for Whisper medium (+ safety margin), the job is marked `failed` with `VRAM_UNAVAILABLE` and the queue advances. The model is not loaded.
- The Whisper model, once successfully loaded, is kept resident across jobs in the same backend lifetime (no reload per job) — matching `CLAUDE.md`'s "Models stay loaded across jobs within same session".
- Phase-2B-specific: Llama is not in scope here, so the "never load both" rule is trivially satisfied. The guard is implemented in a generic, Llama-aware way so Chunk 3 inherits it.

### Video Status Lifecycle (extended from 2A)

```
                                  ┌─────────────┐
                                  │  uploading  │
                                  └──────┬──────┘
                                         │ upload complete
                                         ▼
                                  ┌─────────────┐
                          ┌──────►│  imported   │  (terminal in 2A)
                          │       └──────┬──────┘
                          │              │ auto-pickup (2B)
                          │              ▼
                          │       ┌─────────────┐
                          │       │   queued    │◄──── retry / startup sweep
                          │       └──────┬──────┘
                          │              │ worker picks up
                          │              ▼
                          │       ┌──────────────┐
                          │       │ transcribing │
                          │       └──────┬───────┘
                          │              │
                          │      ┌───────┴───────┐
                          │      ▼               ▼
                          │  ┌───────┐       ┌────────┐
                          │  │ ready │       │ failed │──► user clicks Retry ───┐
                          │  └───────┘       └────────┘                          │
                          │                                                      │
                          └──────────────────────────────────────────────────────┘
```

States added in this chunk: `queued`, `transcribing`, `ready`.
States carried forward from 2A: `uploading`, `imported`, `failed`.
The `failed` state is shared between import failures (2A) and transcription failures (2B), distinguished by the machine-readable error code on the record.
States introduced by later chunks (`analyzing`, `done`, etc.) are explicitly out of scope here. The schema must accommodate future statuses without migration.

### Out of Scope

- Transcript viewer UI (Chunk 2C).
- Click-to-seek on transcript words (Chunk 2C).
- Cancellation of running or queued transcriptions (deferred — delete-video cascade is the escape valve).
- Re-transcription of an already-`ready` video (deferred — idempotent skip; no "Re-transcribe" button).
- Multi-stage pipeline (Llama analysis, export) — Chunks 3+.
- Concurrent transcription of multiple videos on the same GPU (deferred — sequential FIFO only).
- Automatic retry-with-backoff on failure (deferred — user-driven retry only).
- Restart-loop / poison-video detection (deferred — sweep is unconditional; restart counter is a hardening pass).
- Segment-level partial-resumption (deferred — stage-level atomic; on restart, transcription re-runs from the start).
- Whisper int8 fallback when VRAM is constrained (deferred — `CLAUDE.md` flags this as the preferred fallback but it is a hardening pass; 2B fails fast instead).
- Multiple GPU support / GPU selection UI (deferred).
- WebSocket authentication or rate limiting (single-user local app; deferred).
- Progress notifications outside the active tab (desktop notifications, etc.) — deferred.

---

## UI/UX Direction

All visual decisions conform to `DESIGN.md` (Vivid Velocity). This section maps that system to the new 2B surfaces — it does not introduce new tokens, colors, or fonts. The 2A library card layout, dimensions, hover treatment, and component vocabulary are reused; this chunk only adds new content inside the existing card and one new endpoint-level UI affordance (retry).

### Surfaces in Scope

This chunk introduces no new pages. The progress surface lives entirely inside the existing 2A video card, in the library grid.

### Component Mapping to DESIGN.md

| UI element | Vivid Velocity component |
|---|---|
| Progress bar fill | Solid Electric Purple (`primary` / `primary-container`) per DESIGN.md "Primary = AI processing / progress" |
| Progress bar track | `surface-container-high` (subtle contrast against card surface) |
| Progress percent text | `code-sm` (JetBrains Mono 13/18) — reinforces "pro-suite" precision |
| ETA text | `body-sm` (Inter 14/20) muted via `on-surface-variant` |
| Stage label | `label-caps` (JetBrains Mono 12/16, weight 600, 0.05em tracking, uppercase) |
| Queue position pill | `label-caps` on `surface-container-highest` background, secondary text |
| Status chip `queued` | Tertiary-tinted (`tertiary-container` @ 24% bg, `tertiary` text) — DESIGN.md Tertiary is "Caution Yellow / waiting" |
| Status chip `transcribing` | Primary-tinted with subtle pulse — DESIGN.md "Active Indicators" pattern. Replaces the static chip during active processing. |
| Status chip `ready` | Secondary-tinted (`secondary-container` @ 24% bg, `secondary` text) — Viral Green for completion |
| Status chip `failed` | Error-tinted (already defined in 2A) — now also surfaces a short error message below the chip |
| Retry button | Ghost-style button with 1px `primary` border, `primary` text. Same dimensions as the existing card delete icon button for visual rhythm. |
| Inline error message | `body-sm` in `error` color, max 2 lines with ellipsis if longer; full message visible on hover/focus via title attribute |
| "Picking up where we left off" hint | `body-sm` muted in `on-surface-variant`, shown for 4 seconds after auto-requeue, fades out per DESIGN.md standard ease |

### Progress Bar Treatment (the central visual element of this chunk)

The progress bar replaces the status chip on the thumbnail while status is `transcribing`. Layout:

```
┌─────────────────────────────────────────────┐
│  [thumbnail with darker overlay]            │
│                                             │
│         TRANSCRIBING                        │  ← label-caps, centered, on-surface
│         47%                                 │  ← code-sm, large (24px), centered
│         ~3 min left                         │  ← body-sm muted, centered
│                                             │
│  ━━━━━━━━━━━━━━━━━━━░░░░░░░░░░░░░░░░░░░░░░ │  ← progress bar at bottom of thumbnail
│  (Electric Purple fill, 4px tall)           │
└─────────────────────────────────────────────┘
│  [video title]                              │
│  1.2 GB · 23 minutes · 2 hours ago          │  ← unchanged from 2A
└─────────────────────────────────────────────┘
```

- Thumbnail gets a 40%-black overlay (`scrim` @ 40% per DESIGN.md) to ensure overlay text is legible regardless of source brightness.
- The progress bar itself sits as a thin 4px strip at the bottom of the thumbnail (inside the thumbnail bounds, above the metadata region).
- Bar uses MUI `LinearProgress` with a custom track and fill color drawn from the Vivid Velocity tokens — no hardcoded colors.
- Updates animate smoothly between frames (CSS transition on the fill `transform`) but the underlying state is a discrete percent emitted by the backend.
- When status transitions to `ready` or `failed`, the bar and overlay are removed and the standard chip returns — same component pattern as 2A.

### Queue Position Treatment

When status is `queued`, the thumbnail does NOT get the progress overlay. Instead, a small pill sits in the top-right of the thumbnail (where the duration mono-pill currently sits in 2A — they swap, and the duration moves to the bottom-right): `2ND IN QUEUE` (label-caps, `surface-container-highest` background).

The first-in-queue (next to run) shows `NEXT UP` in tertiary-tinted color to emphasize urgency.

### Status Chip Mapping (full table, extending 2A)

| Status | Token source | Chip background | Chip text/dot | Notes |
|---|---|---|---|---|
| `uploading` | DESIGN.md Primary | `primary-container` @ 24% | `primary` | (carried from 2A) |
| `imported` | DESIGN.md Secondary | `secondary-container` @ 24% | `secondary` | (carried from 2A) — visible only briefly before auto-pickup |
| `queued` | DESIGN.md Tertiary | `tertiary-container` @ 24% | `tertiary` | new — paired with queue-position pill |
| `transcribing` | DESIGN.md Primary | (chip is replaced by progress overlay) | — | new — overlay treatment above |
| `ready` | DESIGN.md Secondary | `secondary-container` @ 24% | `secondary` | new — distinguishes from `imported` by label text only |
| `failed` | DESIGN.md Error | `error-container` @ 24% | `error` | (carried from 2A) — now paired with Retry button + error message |

### Interaction Patterns

**Progress reconnect (visible behavior)**
- On page load / navigation back, the bar appears within 1 second at the correct percent — no animation from 0%.
- On WS reconnect, the bar may briefly show a "syncing…" subtle dot before snapping to actual position. No replay of historical events is visible to the user.

**Retry button**
- Appears in the card's metadata row, beside the existing delete icon button.
- Click flips status to `queued` immediately (optimistic), clears the inline error, and the queue position pill appears (or the progress overlay if it goes straight to running).
- Disabled state during the brief request round-trip.
- No confirmation dialog — retry is a non-destructive action (delete already requires confirmation, and the failed transcript wasn't persisted).

**Status filter chips (extension of 2A)**
- The existing 2A chip group `[All] [Uploading] [Imported] [Failed]` extends to: `[All] [Importing] [Queued] [Transcribing] [Ready] [Failed]`.
- The 2A `[Uploading]` label becomes `[Importing]` and groups both `uploading` and `imported` (since `imported` is now a near-instant transient state). The new chips map directly to the new status values.
- Existing 2A chip styling rules apply unchanged.

**"Picking up where we left off" hint**
- Shown for 4 seconds on a card that was just auto-requeued by the startup sweep, immediately after the backend restart.
- Appears as a small banner across the bottom of the thumbnail with `body-sm` muted text and a small refresh icon (Lucide, 16px).
- Fades out automatically; no dismiss button.

### Motion

All animation durations and easings come from Vivid Velocity defaults. New motion moments introduced in this chunk:

1. Progress bar fill transition: 600ms ease-out between discrete percent updates (smooths the visual jump between segments).
2. Status chip swap (transcribing → ready/failed): 200ms cross-fade.
3. "Picking up where we left off" hint: 280ms emphatic ease-out fade-in, 4s hold, 400ms ease-out fade-out.
4. Active-state pulse on transcribing chip / queue-position pill: 2s ease-in-out, infinite, opacity 0.6 ↔ 1.0.

All four respect `prefers-reduced-motion: reduce` — animations become instant transitions and the infinite pulse becomes a static state.

### Accessibility (PRD-level requirements)

- The progress bar exposes `aria-valuenow`, `aria-valuemin=0`, `aria-valuemax=100`, and a labeled `role="progressbar"`.
- The percent text is the source of truth for screen readers; the bar is the visual proxy.
- The ETA is announced via a polite live region whose contents update at most every 10 seconds (avoids spamming the screen-reader user with every Whisper segment).
- The status chip label is the text content (not just color) — already a 2A guarantee, reinforced here.
- The Retry button is reachable by keyboard; activation requires Enter or Space; visible focus ring per 2A standard.
- Queue-position pill text is readable by screen readers as part of the card's accessible name (e.g., "Video Title — 2nd in queue, awaiting transcription").
- The "Picking up where we left off" hint is also announced via the polite live region (single fire on appearance).
- Reduced motion is honored on every animation introduced in this chunk.

### Design System Compliance Checklist (for Gate 3)

Verified during QA:

- [ ] No hex colors hardcoded in component code — all from theme tokens.
- [ ] Progress bar uses MUI `LinearProgress` with theme tokens for both track and fill — no inline color.
- [ ] No font sizes outside the Vivid Velocity scale.
- [ ] All icons are Lucide React (no emoji, no custom one-offs).
- [ ] Status chip colors match the mapping table above.
- [ ] `prefers-reduced-motion` honored on all four new motion moments.
- [ ] Progress overlay scrim uses `scrim` token, not a hardcoded `rgba(0,0,0,0.4)`.
- [ ] Queue-position pill uses `surface-container-highest` background, not a hardcoded gray.

---

## Technical Constraints

### Performance

- Whisper medium throughput: ≥50 source-words/minute sustained (verifiable on a known reference clip).
- Frontend progress update latency: ≤1 second from backend Whisper segment completion to bar update on screen (excluding WS connection establishment).
- Snapshot-on-reconnect latency: bar reflects correct position within 1 second of page load or WS reconnect.
- Startup sweep latency: any `transcribing` records left by a crashed process are returned to `queued` within 10 seconds of lifespan startup.

### Storage & Disk

- Transcript records persist in MongoDB. Document size is bounded by the source video duration; the 16MB BSON limit is sufficient for videos up to ~12 hours at typical conversational density. Videos over that limit are out of scope for this chunk (2A's 4-hour cap is well under).
- No additional disk usage in `media/` beyond what 2A already produces — transcripts live in the database.

### GPU & VRAM

- Whisper medium float16 (CTranslate2): targeted at ≤2.2 GB VRAM. Configurable budget via environment variable (default 2200 MB).
- The "never load both Whisper and Llama" rule (per `CLAUDE.md`) is structurally enforced via the VRAM guard. Llama is not loaded in this chunk, so the constraint is trivially satisfied; the guard is implemented in a forward-compatible way.
- The Whisper model loads on first job and remains resident across subsequent jobs in the same backend lifetime.
- A `VRAM_UNAVAILABLE` failure on a single job does not unload the model from other jobs — the model is loaded once at startup of the first eligible job. The failure means we could not even allocate enough for that first load.

### Security & Privacy

- Local-first, single-user. No authentication on WebSocket connections (matching the rest of the app).
- WebSocket endpoint validates that the requested job ID exists before subscribing — invalid IDs receive an error event and a close.
- No external data transmission introduced by this chunk. Whisper runs entirely on-device.

### Integration Requirements

- Frontend ↔ Backend WebSocket message envelope follows the existing API envelope shape (`{ data, error, meta? }`) where appropriate, or a typed message format (`{ type, ...payload }`) for the WS-specific event stream. The exact contract is defined in the Tech Doc (Gate 2).
- TypeScript types for transcript records, WebSocket message types, and the new video status values are generated from the backend's Pydantic schemas — no hand-mirrored types (carried-forward 2A pattern).
- All errors return machine-readable codes (e.g., `TRANSCRIPTION_FAILED`, `VRAM_UNAVAILABLE`, `AUDIO_DECODE_FAILED`, `JOB_NOT_FOUND`, `INVALID_TRANSITION`).

### Compatibility

- Browsers: same as 2A (latest Chrome, Firefox, Edge on Windows 11).
- WebSocket support: assumed (no fallback to long-polling).
- GPU: NVIDIA RTX 2000 Ada (8 GB nameplate, ~7.0 GB usable) on Windows 11. The VRAM budget and pynvml integration target this hardware specifically; the chunk does not promise correctness on other GPUs.

---

## MVP Scope & Phasing

### Phase 1: This Chunk (2B) — Required to Ship

- Auto-trigger transcription on `imported` videos
- Whisper medium integration with word-level timestamps + confidence
- Sequential FIFO queue with persistent ordering
- WebSocket endpoint with snapshot-on-subscribe + live progress events
- `useTranscriptionProgress(videoId)` hook in shared kernel
- Status badge transitions (queued, transcribing, ready) + progress overlay on card
- VRAM guard (hard lock, configurable budget)
- Restart sweep (auto-requeue `transcribing` videos on lifespan startup)
- Retry button on `failed` cards
- Transcript persistence to MongoDB (atomic write on completion)

**MVP Definition:** A user can upload three videos in a row, walk away, and come back to all three transcribed and `ready`. The progress bar on each card was visible and accurate throughout. Killing the backend mid-job and restarting it picks up the work without manual intervention. A deliberately corrupt file fails clearly with a Retry button.

### Phase 2: Chunk 2C (Next)

- Transcript viewer UI (`/video/[id]` route)
- Word-level rendering with confidence color-coding (heatmap)
- Click-to-seek stub
- Reads the transcript persisted by this chunk — no contract changes

### Future Considerations

- Cancellation of running/queued transcriptions (currently delete-video is the only escape)
- Re-transcription button on `ready` videos (currently idempotent skip)
- Segment-level partial-resumption (currently stage-level atomic)
- Whisper int8 fallback under VRAM pressure
- Concurrent transcription on multi-GPU rigs
- Restart-loop / poison-video detection with restart counter
- Automatic retry-with-backoff on transient failures

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| CUDA driver crash mid-transcription kills the backend process | Med | High | Restart sweep auto-requeues; user sees brief "picking up where we left off" hint. Stage-level atomic means no partial state to reconcile. |
| Whisper model load exceeds VRAM budget due to other GPU consumers | Med | Med | VRAM guard fails fast with `VRAM_UNAVAILABLE`; user closes other consumers and retries. No driver crash. |
| WebSocket connection unstable on flaky local network | Low | Med | Snapshot-on-reconnect makes recovery transparent; no replay buffer to manage. Frontend reconnects with exponential backoff. |
| Long video (~90 min) exceeds 16 MB BSON limit on transcript document | Low | High | Hard cap on source video duration is 4 hours (2A). At ~150 words/min and ~200 bytes/word the worst case is ~7 MB — well under the BSON limit. If a future change permits longer source videos, split transcript across multiple documents. |
| ETA estimation is wildly inaccurate early in the job | High | Low | Show ETA only after first segment completes; use simple linear extrapolation (`elapsed / percent × (100 − percent)`); accept user-visible drift as Whisper segments aren't uniform-duration. Acceptable for MVP. |
| Queue starvation: a video stuck in `transcribing` forever blocks the rest | Low | High | Transcription wraps in a wall-clock timeout (configurable, default 4× source duration). On timeout, mark `failed` with `TRANSCRIPTION_TIMEOUT`, advance queue. |
| Auto-pickup races with delete (user deletes video while pipeline is picking it up) | Low | Med | Pickup uses an atomic MongoDB `findOneAndUpdate` with `status=queued` precondition; if delete fires first, pickup is a no-op (document not found). |
| User experience confused by 4-second "picking up where we left off" message disappearing | Low | Low | Banner uses standard fade pattern; the underlying status remains `queued`/`transcribing` and is visible without the banner. |

---

## Dependencies & Blockers

**Dependencies:**

- Chunk 2A (Video Import Foundation) — merged. This chunk extends the `videos` collection and the library card UI, both of which 2A established.
- faster-whisper (Python package) — to be installed via `uv sync --extra ai`.
- pynvml (Python package) — for VRAM querying. Added by this chunk.
- Whisper medium model file (~1.5 GB) — downloaded manually via the existing `scripts/download_models.py` per Phase 1 README. User must run download before first use.
- CUDA 12.x toolkit + cuDNN 9.x — installed per Phase 1 open items. User has confirmed installation as a prerequisite to starting this chunk.
- pydantic-to-typescript codegen pipeline — established by 2A. New schemas this chunk introduces will be codegen'd identically.
- `DESIGN.md` (Vivid Velocity) — extended with no new tokens; this chunk uses existing tokens only.

**Known Blockers:**

- None expected. If CUDA/cuDNN are not installed at implementation start, the implementation pauses until the user installs them. (Verified pre-PRD that the user understands this requirement.)

---

## Verification (Gate 3)

This PRD will be considered satisfied when, in a single demo session:

1. Upload an MP4 → within 2 seconds the card shows `queued` (if a job is in flight) or `transcribing` (if not). No user action between upload completion and transcription starting.
2. Upload three videos in rapid succession → the first transcribes, the other two show `queued` with positions "Next up" and "3rd in queue". As each completes, the next begins and positions shift.
3. The transcribing card shows a progress bar with percent and ETA. The bar advances monotonically and reaches 100% before the card flips to `ready`.
4. Refresh the browser mid-transcription → the bar resumes at the correct percent within 1 second (verified by comparing against a stopwatch).
5. Inspect the transcript record in MongoDB after `ready` → it contains ordered segments with ordered words; each word has start, end, and confidence; total word count is ≥50 × source-video-minutes.
6. Verify timestamp accuracy by checking three randomly-selected words in the transcript against the source audio at those timestamps (±100ms acceptable).
7. Run `nvidia-smi` during transcription → allocated VRAM is ≤ 7.0 GB.
8. While a transcription is running, `taskkill /F /PID <uvicorn>`, then `uv run uvicorn app.main:app --reload`. Within 10 seconds of startup, the killed video is back to `queued` and the worker picks it up. The `lastProgressPercent` from before the kill is preserved on the record.
9. Provide a deliberately corrupt audio file (e.g., a renamed text file) → transcription fails with `AUDIO_DECODE_FAILED`, card shows the error message, Retry button is visible. Click Retry → status returns to `queued`; the same failure recurs (expected); the queue is not blocked by repeated failures.
10. Simulate VRAM pressure (e.g., load another GPU model in a separate process consuming ≥6 GB) → next transcription fails fast with `VRAM_UNAVAILABLE` rather than crashing the driver.
11. Design System Compliance Checklist (UI/UX Direction § Compliance Checklist) passes top-to-bottom — every item ticked.
12. The transcript persisted by this chunk is loadable by Chunk 2C without any contract change (forward-compatibility check — verifiable as a structural assertion in a test, doesn't require 2C UI to exist).

Every acceptance criterion above must have at least one corresponding test (unit, integration, or E2E) in the Verification Report.

---

## Glossary

- **Transcription:** The act of converting the audio track of a video into a sequence of timestamped words with confidence scores, using the Whisper model.
- **Segment:** Whisper's natural output unit — a contiguous span of audio (typically 5–30 seconds) containing one or more words.
- **Word:** A single token from Whisper's word-level output, carrying text, start, end, and confidence.
- **Confidence:** Whisper's per-word probability score in the range 0.0–1.0. Higher means the model is more sure of the recognition.
- **Stage:** A named phase of the overall pipeline. This chunk introduces one stage: `transcription`. Future chunks will add `analysis` and `export`.
- **Job:** A specific execution attempt of a stage on a specific video. A video can have multiple jobs over its lifetime (e.g., on retry).
- **Queue:** The ordered set of videos awaiting transcription, derived from `videos` where `status = queued`, ordered by `createdAt`.
- **Snapshot (WS):** The one-shot event the server sends to a newly-subscribed client describing the current state of the job, enabling instant UI sync without replay.
- **Startup sweep:** The lifespan-startup routine that scans for videos left in `transcribing` by a crashed process and returns them to `queued`.
- **VRAM guard:** The pynvml-backed check that asserts sufficient GPU memory is free before loading the Whisper model. Failing the check marks the job `failed` with `VRAM_UNAVAILABLE`.
- **lastProgressPercent:** A persisted field on the video record that records the most recent percent observed during transcription, used to surface the resumption hint after a restart.
