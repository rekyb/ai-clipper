# Product Requirements Document: Video Import Foundation

**Feature:** Video Import (Phase 2, Chunk 2A)
**Version:** 1.1
**Date:** 2026-05-17
**Author:** Sarah (Product Owner)
**Quality Score:** 93/100
**Design System:** Conforms to `DESIGN.md` (Vivid Velocity) at the project root. No new visual style introduced.

---

## Executive Summary

Video Import is the entry point to the AI Clipper pipeline. Users must be able to bring source material into the system — either by uploading a local file or pasting a YouTube URL — and immediately see it appear in a browsable library with a thumbnail, title, and duration. Without this foundation no downstream feature (transcription, viral analysis, export) has anything to operate on.

This chunk delivers the import flow end-to-end (file in → metadata extracted → record visible in library) plus delete-from-library, so users can manage failed or test imports without manual database edits. Real-time progress streaming, transcription, and transcript viewing are explicitly deferred to Chunks 2B and 2C.

The success of this feature unblocks the rest of Phase 2 and validates the two-runtime contract (frontend ↔ backend) under realistic file-handling load.

---

## Problem Statement

**Current Situation:** The AI Clipper backend skeleton and database exist (Phase 1 complete), but there is no way to get a video into the system. The pipeline cannot be tested end-to-end, the library page has nothing to display, and Phase 2B (transcription) has no input source.

**Proposed Solution:** A two-path import flow — local file upload and YouTube URL ingestion — that validates the source, extracts a thumbnail and duration, and persists a video record. A simple library list page shows the imported videos as cards.

**Business Impact:** Unblocks all downstream features. Establishes the file-handling, validation, and metadata-extraction patterns that Phases 3–5 will build on.

---

## Success Metrics

**Primary KPIs:**
- **Import success rate:** ≥95% of valid MP4/MKV/MOV/AVI/WebM files under 5GB / 4hr complete successfully end-to-end.
- **URL import reliability:** ≥90% of public, non-region-blocked YouTube URLs complete successfully.
- **Library responsiveness:** Library page renders in <500ms with up to 50 video records.
- **Storage clarity:** Every video record displays its file size so users can manage local disk.

**Validation:** Verified manually during Gate 3 with a representative sample (5 file uploads of varying size/duration, 5 YouTube URLs of varying length).

---

## User Personas

### Primary: Solo Content Creator
- **Role:** Single-user, local-first operator (the app owner).
- **Goals:** Bring long-form source video into the system as quickly as possible to start hunting for viral clips.
- **Pain Points:** Existing online tools cost $30–100/month; uploading large files to cloud services is slow and bandwidth-expensive.
- **Technical Level:** Intermediate. Comfortable with a desktop UI; not expected to use a CLI or edit a database.

This is the only persona — the application is single-user and runs locally. No auth, no multi-tenancy.

---

## User Stories & Acceptance Criteria

### Story 1: Upload a local video file

**As a** solo content creator
**I want to** drag a video file into the app (or pick it via a file dialog)
**So that** I can start processing it without leaving my desktop

**Acceptance Criteria:**
- [ ] User can drag-and-drop a file onto the upload area; user can also click to open a native file picker.
- [ ] Supported formats are accepted: MP4, MKV, MOV, AVI, WebM.
- [ ] Files larger than 5GB are rejected with a clear message before upload begins.
- [ ] Files longer than 4 hours are rejected after duration is read.
- [ ] Unsupported codecs (e.g., proprietary or unparseable containers) are rejected with a clear message naming the issue.
- [ ] After successful upload, the video appears in the library list with thumbnail, title, duration, file size, and status.
- [ ] During upload the UI shows a busy state on the upload area so the user knows the action is in progress.

### Story 2: Import a video by YouTube URL

**As a** solo content creator
**I want to** paste a YouTube link and have the video downloaded into the system
**So that** I can clip public source material without manually downloading it first

**Acceptance Criteria:**
- [ ] URL input accepts youtube.com and youtu.be URLs.
- [ ] Non-YouTube URLs are rejected with a clear message stating only YouTube is supported.
- [ ] Invalid or unreachable URLs surface a user-friendly error (not a stack trace).
- [ ] Age-gated, private, or region-blocked videos surface a specific error message identifying the cause.
- [ ] On success, the imported video appears in the library identical in shape to an uploaded file.
- [ ] The video's title is taken from the YouTube metadata, not the URL.

### Story 3: Browse the video library

**As a** solo content creator
**I want to** see all my imported videos at a glance
**So that** I can pick one to work on next

**Acceptance Criteria:**
- [ ] Library page displays a grid of cards, one per video.
- [ ] Each card shows: thumbnail image, title, duration (mm:ss or hh:mm:ss), file size (MB/GB), status badge, created date.
- [ ] Default sort is newest-first by import date.
- [ ] Status filter chips (All / Uploading / Imported / Failed) let the user narrow the list.
- [ ] An empty library shows a friendly empty state pointing at the import controls.
- [ ] If 50+ videos are imported, the page still loads under 500ms (no full-list re-fetch on filter change).

### Story 4: Remove a video from the library

**As a** solo content creator
**I want to** delete videos I no longer need
**So that** failed imports and test files don't clutter my library or fill my disk

**Acceptance Criteria:**
- [ ] Each card exposes a delete action (icon button or menu item).
- [ ] Delete requires explicit confirmation before destructive action.
- [ ] On confirm, the video record is removed from the database AND the underlying source file is removed from disk.
- [ ] Library list updates immediately after delete; deleted video does not reappear on refresh.
- [ ] Delete is idempotent: deleting an already-removed record returns a not-found error, not a crash.

### Story 5: Avoid accidental duplicate imports

**As a** solo content creator
**I want** the app to refuse re-imports of files I already have
**So that** I don't waste disk space on the same source twice

**Acceptance Criteria:**
- [ ] On upload, the file is hashed (content-based, not filename-based).
- [ ] If a video with the same hash already exists, the import is rejected with a message identifying the existing record.
- [ ] On URL import, the same check runs after download — duplicate detection is content-based, not URL-based.
- [ ] The duplicate-rejected file is cleaned up from temporary storage (no orphans).

---

## Functional Requirements

### Core Features

**Feature 1: File Upload**
- Accepts: MP4, MKV, MOV, AVI, WebM containers.
- Hard limits: ≤5GB file size, ≤4 hours duration.
- On accept: extract duration via media inspection, generate a thumbnail from the 10% mark of the video timeline, compute content hash, persist record.
- On reject: surface a specific error code identifying the cause (oversize, too long, unsupported codec, duplicate).

**Feature 2: YouTube URL Import**
- Host validation: accept only `youtube.com` and `youtu.be`.
- Title and source metadata are pulled from the platform — not constructed from the URL.
- Downloaded file is treated identically to an uploaded file from the duration/thumbnail/hash step onward.
- Error categories surfaced distinctly: invalid URL, unsupported host, network failure, age-gated, region-blocked, private, removed.

**Feature 3: Video Library**
- Grid layout with cards.
- Card content: thumbnail, title, duration, file size, status badge, created date, delete action.
- Default order: newest-first by import date.
- Status filter chips: All, Uploading, Imported, Failed.
- Empty state: friendly call-to-action pointing at import controls.

**Feature 4: Delete Video**
- Confirmation required before destructive action.
- Removes both the database record and the source file on disk.
- Idempotent and surfaces a not-found error gracefully if the record is already gone.

### Video Status Lifecycle (for this chunk)

- `uploading` — file is being written to disk (upload in flight, or yt-dlp download in progress).
- `imported` — file is on disk, duration and thumbnail are extracted, record is complete and ready for downstream stages.
- `failed` — import did not complete; record remains visible so the user can see and delete it.

Statuses introduced by later chunks (`transcribing`, `ready`, etc.) are explicitly out of scope here. The schema must accommodate future statuses without migration.

### Out of Scope

- New visual styles or design tokens (everything conforms to `DESIGN.md`).
- Transcription (Chunk 2B).
- WebSocket-based real-time progress updates (Chunk 2B).
- Transcript display (Chunk 2C).
- Video player (Phase 3).
- Clip browsing or scoring (Phase 3).
- Topic search, advanced filters, history pagination (Phase 6).
- Non-YouTube URL sources (post-MVP).
- Re-encoding or transcoding rejected codecs (out of scope; reject and inform).
- Bulk upload (multiple files at once).
- Resumable uploads / chunked uploads.
- User-selectable thumbnail frame (auto-pick at 10% for this chunk).

---

## UI/UX Direction

All visual decisions conform to `DESIGN.md` (Vivid Velocity). This section maps that system to the Video Import surfaces — it does not introduce new tokens, colors, or fonts.

### Page Layout

The Library is the application's home page. It uses Vivid Velocity's **dashboard 12-column grid** with **margin-desktop (32px)** outer padding and **gutter (20px)** between columns.

The page has two stacked regions:

1. **Import Panel** (top, full width) — a single glassmorphic panel (Mid-Level surface) containing two side-by-side controls on desktop, stacked on mobile/narrow:
   - **Upload dropzone** (left, ~60% width)
   - **URL import form** (right, ~40% width)
2. **Library Grid** (below, full width) — the video card collection with a header row above it containing the page title and the **status filter chip group**.

Vertical rhythm: `lg` (48px) between Import Panel and Library; `md` (24px) between the library header row and the card grid.

### Component Mapping to DESIGN.md

| UI element             | Vivid Velocity component                                                                                       |
|------------------------|----------------------------------------------------------------------------------------------------------------|
| Page title             | `headline-lg` (Hanken Grotesk 32/40, weight 700, -0.01em)                                                      |
| Section subtitle       | `title-md` (Hanken Grotesk 20/28, weight 600)                                                                  |
| Body text & form labels| `body-sm` (Inter 14/20)                                                                                        |
| Card title (video name)| `title-md` truncated to one line                                                                               |
| Duration, file size, timestamps | `code-sm` (JetBrains Mono 13/18) — reinforces "pro-suite" precision                                 |
| Filter chip / status chip labels | `label-caps` (JetBrains Mono 12/16, weight 600, 0.05em tracking, uppercase)                          |
| Upload dropzone surface | Mid-Level glassmorphic surface (`surface-container` at 80% with 1px outline-variant border, dashed when empty)|
| Library video card      | Mid-Level glassmorphic surface with 1rem (16px) radius — "Content object" radius per DESIGN.md §Shapes        |
| Buttons (primary)       | Solid Electric Purple (`primary-container`) with `on-primary-container` text. `rounded.DEFAULT` (8px)         |
| Buttons (secondary/cancel) | Ghost-style with 1px `outline-variant` border, `on-surface-variant` text                                   |
| Destructive button (Delete confirm) | Ghost button with `error` text and 1px `error` border on rest; `error-container` fill on hover     |
| Delete confirm dialog   | High-Level modal: glassmorphic surface with 20px backdrop blur and subtle Primary glow per DESIGN.md          |
| Status chip "uploading" | Primary-tinted (Electric Purple) — DESIGN.md treats Primary as "AI processing / progress"                     |
| Status chip "imported"  | Secondary-tinted (Viral Green, `secondary` / `on-secondary-container`) — DESIGN.md reserves Secondary for success states |
| Status chip "failed"    | Error-tinted (`error-container` bg, `on-error-container` text)                                                |
| Filter chips            | DESIGN.md "small low-contrast tags, vibrant only when selected" — selected chip uses Electric Purple fill     |
| Empty state             | Centered Lucide icon (48px, `outline` color) + `title-md` heading + `body-sm` description + ghost CTA          |
| Loading skeleton        | Mid-Level surfaces matching card bounding boxes, gentle opacity pulse (1.2s ease-in-out)                       |
| Icons                   | Lucide React. 16px inline, 20px in buttons/chips, 24px in headers, 48px in empty states. 1.5px stroke         |

### Interaction Patterns

**Upload dropzone**
- Idle: dashed 1px `outline-variant` border on a Mid-Level glass surface. Centered icon (Upload, 24px) + `body-sm` instruction ("Drop a video here or click to browse") + `label-caps` hint ("MP4 MKV MOV AVI WEBM · max 5 GB · 4 h").
- Drag-over: border switches to solid Electric Purple (`primary`) at 2px; surface receives a subtle Primary-tinted inner glow per DESIGN.md "Active Indicators" pattern.
- Busy (uploading): dropzone is disabled; an overlay shows a 20px Electric Purple spinner + `body-sm` "Uploading…". Cursor: `not-allowed`.
- Rejection: inline error in `error` color appears below the dropzone (`body-sm`), auto-cleared on next user interaction.

**URL import form**
- A single input field (DESIGN.md input pattern: darker than surface, bottom border highlights to Primary on focus) + a `filled` primary button.
- Client-side prefilter: detect non-YouTube hosts and disable submit with inline hint. Server is still authoritative.
- Busy state mirrors the dropzone — spinner on the button, input read-only.

**Library card**
- At rest: Mid-Level glass surface, 16px radius, 1px low-opacity border.
- Hover: border illuminates to Electric Purple at 60% opacity per DESIGN.md ("video preview should have a 1px border that illuminates in Purple when hovered"). Cursor: `pointer`.
- Card content top-to-bottom: 16:9 thumbnail with absolute-positioned status chip (top-left) and duration mono-pill (bottom-right of thumbnail), then 12px padding region with title, file size in `code-sm`, created date in `body-sm` muted, and a delete icon button in the top-right corner of the metadata row.
- The whole thumbnail+title region is the click target for "open video" (Phase 3 will wire navigation; for 2A clicking is a no-op stub).

**Status filter chips**
- Chip group: `[All] [Uploading] [Imported] [Failed]`.
- All chips use `label-caps` typography.
- Unselected: `surface-container-high` bg, `on-surface-variant` text.
- Selected: Electric Purple (`primary-container`) bg, `on-primary-container` text — per DESIGN.md "becoming vibrant only when selected".
- Single-select. "All" is the default and is exclusive with the others.

**Delete confirm dialog**
- High-Level glassmorphic modal, 480px max-width, centered.
- Content: `title-md` heading "Delete \"{video title}\"?" + `body-sm` body "This removes the source file from your disk. This cannot be undone."
- Action row right-aligned: ghost "Cancel" + destructive primary "Delete".
- Open animation: 280ms emphatic ease-out, slight upward translate (8px → 0) + fade. Honors `prefers-reduced-motion`.
- Escape key closes. Focus traps inside dialog. Initial focus on Cancel (safer default).

**Empty state**
- Shown when the library is empty AND no filter is active.
- Centered in the library region, max-width 320px: Lucide icon `FilmStrip` 48px in `outline` color, `title-md` "Your library is empty", `body-sm` "Drop a video above or paste a YouTube URL to get started." No CTA button — the import panel above is the CTA.
- Filtered empty (e.g., filter=Failed with no failures): show a different copy variant, no icon — just `body-sm` muted "No videos with this status."

**Loading state (initial library fetch)**
- Skeleton grid of 6 cards. Each skeleton mirrors the real card bounding boxes (thumbnail block + 2 text rows). Animation: opacity 0.4 ↔ 0.7 over 1.2s ease-in-out. Disable when `prefers-reduced-motion: reduce`.

**Error state (library fetch failure)**
- Replace the card grid with an inline alert: `error-container` background, `on-error-container` text, `body-sm`, with a ghost "Retry" button. Title in `title-md`: "Couldn't load your videos."

### Color Mapping for Status

Per DESIGN.md, Primary = "AI processing / progress", Secondary = "success / Export Complete", Error = failure. The mapping applied here:

| Status      | Token source           | Chip background           | Chip text/dot               |
|-------------|------------------------|---------------------------|-----------------------------|
| `uploading` | DESIGN.md Primary      | `primary-container` @ 24% | `primary`                   |
| `imported`  | DESIGN.md Secondary    | `secondary-container` @ 24% | `secondary`                |
| `failed`    | DESIGN.md Error        | `error-container` @ 24%   | `error`                     |

A 6px solid dot in the chip's text color sits to the left of the label on status chips. Filter chips do not show a dot (they use only the selected/unselected color shift).

### Motion

All animation durations and easings come from Vivid Velocity defaults. No custom keyframes are introduced in this chunk. The four motion moments in scope:

1. Card hover (border illuminate): 180ms standard ease-out.
2. Dropzone drag-over (border + glow): 120ms ease-out.
3. Filter chip selection: 120ms ease-out.
4. Delete dialog open: 280ms emphatic ease-out.

All four respect `prefers-reduced-motion: reduce` — animations become instant transitions.

### Accessibility (PRD-level requirements)

- All interactive elements have visible focus rings using Electric Purple at 2px offset 0.
- All form inputs have programmatic labels (visually shown above the input).
- Dropzone is reachable by keyboard: Tab to focus, Enter/Space opens the file picker.
- Filter chips are a single-select radio group semantically.
- Delete dialog traps focus; Escape closes; initial focus on Cancel; the destructive action requires explicit click (no Enter-to-confirm).
- All thumbnails carry alt text (default = video title; placeholder for `uploading` state = "Thumbnail loading").
- Color is never the only indicator of status — every status chip carries a label, and the failed state additionally shows the human-readable error message.

### Design System Compliance Checklist (for Gate 3)

Verified during QA:

- [ ] No hex colors hardcoded in component code — all from theme tokens.
- [ ] No font sizes outside the Vivid Velocity scale.
- [ ] All icons are Lucide React (no emoji, no custom one-offs).
- [ ] Status chip colors match the mapping table above.
- [ ] Hover/focus states present and visible on every interactive element.
- [ ] `prefers-reduced-motion` honored.
- [ ] Glassmorphic surfaces use DESIGN.md's tonal/blur recipe — no ad-hoc shadows.
- [ ] Thumbnail aspect ratio is 16:9 with object-fit cover.
- [ ] Card radius is 16px (Content object), button radius is 8px (UI control) — per DESIGN.md Shapes section.

---

## Technical Constraints

### Performance
- Library page renders <500ms with up to 50 records.
- Thumbnail extraction completes within 5s for any file under the 5GB / 4hr cap.
- YouTube download is bound by network throughput; the UI must not block during the download.

### Storage & Disk
- Source files live in the configured originals directory on the local filesystem.
- Every video record includes file size in bytes; the UI displays it human-readably (MB/GB).
- Delete must remove the on-disk file synchronously with the database record removal.

### Security & Privacy
- Local-first, single-user. No authentication required.
- No external data transmission beyond yt-dlp's own fetches to YouTube.
- Uploaded filenames are sanitized before being used on disk (no path traversal).

### Integration Requirements
- Frontend communicates with backend over HTTP using the existing API envelope (`{ data, error, meta? }`).
- TypeScript types for video records are generated from the backend's schema definitions — no hand-mirrored types.
- All errors return machine-readable codes (e.g., `FILE_TOO_LARGE`, `DURATION_EXCEEDED`, `UNSUPPORTED_FORMAT`, `DUPLICATE_VIDEO`, `INVALID_URL`, `UNSUPPORTED_HOST`, `DOWNLOAD_FAILED`, `NOT_FOUND`).

### Compatibility
- Browsers: Latest Chrome, Firefox, Edge on Windows 11 (the operator's environment).
- File system: Windows paths must be handled correctly (forward/backslash, drive letters).

---

## MVP Scope & Phasing

### Phase 1: This Chunk (2A) — Required to Ship
- File upload with drag-drop and file picker
- YouTube URL import
- Duration + thumbnail extraction
- Content-hash duplicate detection
- Video library list with cards, status filter, newest-first sort
- Delete video (record + file)
- Error reporting with machine-readable codes
- File size display

**MVP Definition:** A user can drag a 1GB MP4 onto the page OR paste a YouTube URL, see it appear in the library with a thumbnail and duration, and delete it again. Both flows succeed for valid input and fail clearly for invalid input.

### Phase 2: Chunk 2B (Next)
- WebSocket progress streaming during upload/download
- Transcription pipeline + Whisper integration
- Status lifecycle extends to `transcribing`, `ready`

### Phase 3: Chunk 2C
- Transcript viewer page
- Word-level rendering with timestamps + confidence

### Future Considerations
- Non-YouTube URL sources (Vimeo, Twitch, etc.)
- Bulk upload
- Resumable / chunked uploads for very large files
- User-selectable thumbnail frame
- Re-encoding fallback for unsupported codecs

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| yt-dlp breakage from YouTube site changes | Med | High | Pin a known-working yt-dlp version; document the upgrade procedure; surface download errors with the underlying message so the user knows when to update. |
| Large-file upload exhausts memory | Low | High | Stream uploads to disk rather than buffering in memory; enforce 5GB cap at the request boundary. |
| Thumbnail extraction fails for exotic codecs | Med | Med | Always validate format before extraction; on failure, mark video `failed` with a clear error and let the user delete it. |
| Content hash on multi-GB file is slow | Med | Low | Hash while the file is being written to disk, not as a separate pass. Accept a small upload-time cost in exchange for reliable duplicate detection. |
| Windows path edge cases (long paths, unicode) | Low | Med | Sanitize filenames; test with unicode and >260-char path scenarios; surface clear errors if the OS rejects a path. |
| User imports the same video twice expecting separate records | Low | Low | Duplicate-rejection error message includes the existing video's title so the user understands what happened. |

---

## Dependencies & Blockers

**Dependencies:**
- FFmpeg / ffprobe installed on the host (already in place per Phase 1 memory).
- yt-dlp installed (will be added by this chunk).
- MongoDB running locally with the `videos` collection initialized (already in place per Phase 1).
- Existing API envelope and shared kernel from Phase 1.
- `DESIGN.md` (Vivid Velocity) established at project root — used for every visual decision.

**Known Blockers:**
- None. All Phase 1 prerequisites are in place per `docs/memory.md`.

---

## Verification (Gate 3)

This PRD will be considered satisfied when, in a single demo:
1. The user drags a valid MP4 onto the upload area → record appears in the library with thumbnail, title, duration, file size, status `imported`.
2. The user pastes a YouTube URL → yt-dlp downloads → record appears in the library identically to (1).
3. The user attempts to upload a 6GB file → rejected with `FILE_TOO_LARGE`.
4. The user attempts to upload a 5hr video → rejected with `DURATION_EXCEEDED`.
5. The user attempts to upload the same file twice → second attempt rejected with `DUPLICATE_VIDEO` referencing the first record.
6. The user pastes a Vimeo URL → rejected with `UNSUPPORTED_HOST`.
7. The user deletes a video → record and file are both removed; library updates without refresh.
8. Status filter chips correctly narrow the library list.
9. Empty library shows the empty-state CTA.
10. Design System Compliance Checklist (UI/UX Direction § Compliance Checklist) passes top-to-bottom — every item ticked.

Every acceptance criterion above must have at least one corresponding test (unit or E2E) in the Verification Report.

---

## Glossary

- **Source file:** The original video uploaded or downloaded by the user, stored under the originals directory.
- **Content hash:** A deterministic fingerprint (SHA-256) of the source file bytes, used to detect duplicates.
- **Thumbnail:** A still image extracted from the source video, displayed on library cards.
- **Library:** The grid of cards on the application's main page showing all imported videos.
- **Import:** The complete flow from user action (drop file / submit URL) to a persisted, browsable video record.
