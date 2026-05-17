# AI Clipper — Project CLAUDE.md

## Overview

Local-first AI video clipping tool. Identifies viral-worthy 30-60s segments from long-form videos and exports TikTok-ready clips with animated captions. Two-runtime monorepo: Next.js frontend + FastAPI backend.

## Development Workflow

All work (except critical hotfixes) follows this gated workflow before any implementation begins.

### Gate 1: PRD (Product Requirements)

- **Location:** `docs/features/[feature-name]/[feature-name]-prd.md`
- **Skills:** Use `/product-requirements` to draft requirements. Use `/ui-ux-pro-max` to provide UI/UX direction (layout, interaction patterns, visual guidelines) as part of the PRD.
- **Tone:** Tech-agnostic. Describe the problem, user stories, acceptance criteria, success metrics, and UI/UX direction. No implementation details.
- **Visual coherence:** Every PRD must reference `DESIGN.md` for style, color palette, typography, spacing, and component patterns. New features conform to the established design system — never introduce a new visual style per feature.
- **Review role:** Act as Head of Product. Evaluate completeness, clarity, user value, edge cases, and visual consistency with the design system.
- **Approval:** User must explicitly approve the PRD before proceeding to Gate 2.

### Gate 2: Technical Documentation

- **Location:** `docs/features/[feature-name]/[feature-name]-technical-docs.md`
- **Skills:** Use `/backend-development` for BE sections, `/frontend-design` for FE sections
- **Input:** Must reference and implement the approved PRD from Gate 1
- **Content:** Architecture decisions, data models, API contracts, component breakdown, error handling, migration steps
- **Review role:** Act as Technical Lead. Evaluate feasibility, scalability, consistency with existing patterns, and alignment with the PRD.
- **Approval:** User must explicitly approve Tech Docs before implementation begins.

### Confidence Gate (applies at both gates)

Before presenting any document for approval, self-assess confidence (0-100%):
- **90%+:** Present the document for review.
- **Below 90%:** STOP. Do not present or implement.
  1. State what is unclear and your current confidence level
  2. Ask targeted questions to the user
  3. If still unclear after answers, propose 2-3 interpretations and let user pick
  4. Use `/brainstorming` if the gap is about requirements or design direction
  5. Only proceed once confidence reaches 90%+

### Gate 3: Verification Report

- **Trigger:** After implementation is complete, before marking a task done or committing
- **Content:** A brief report showing each PRD acceptance criterion and the test(s) that prove it was met
- **Review role:** Act as QA Lead. Confirm no criterion is unverified.
- **Approval:** User must explicitly approve before merge.

### Workflow Summary

```
User request
  -> /brainstorming (if context unclear)
  -> Gate 1: PRD (/product-requirements, review as Head of Product)
  -> User approves PRD
  -> Gate 2: Tech Docs (/backend-development + /frontend-design, review as Tech Lead)
  -> User approves Tech Docs
  -> Implementation (TDD, feature-folder isolation)
  -> Gate 3: Verification Report (review as QA Lead)
  -> User approves Verification Report
  -> Merge
```

### Hotfix Exception

Critical bugs that block users may skip Gates 1-2. Requirements:
- Tag commit with `hotfix:` prefix
- **Gate 3 (Verification) is mandatory** — provide a Verification Report proving the fix works and no regressions introduced before merge
- Write a retroactive PRD + Tech Doc within the same PR or follow-up PR
- Keep scope minimal — fix only the broken behavior

## Stack

- **Frontend:** Next.js 15 (App Router), TypeScript strict, MUI v7, SWR, WebSocket (native)
- **Backend:** FastAPI (Python 3.12+), Pydantic v2, faster-whisper, llama-cpp-python, ffmpeg-python, OpenCV
- **Database:** MongoDB (local) + Mongoose (frontend) / Motor (backend)
- **AI Models:** Whisper medium (CTranslate2), Llama 3.1 8B Q5_K_M (GGUF)
- **Tooling:** pnpm (frontend), uv (backend), ruff + mypy (Python lint/types)
- **Testing:** Vitest (frontend unit), pytest (backend), Playwright (E2E)

## Project Structure

```
ai-clipper/
├── frontend/           # Next.js 15 app
│   ├── src/app/        # App Router pages
│   ├── src/features/   # Feature folders (import/, clips/, export/, history/)
│   ├── src/components/ # Shared UI components (ComponentName/index.tsx)
│   ├── src/hooks/      # Shared hooks (use[Name].ts)
│   ├── src/lib/        # Shared kernel: API client, WebSocket, primitives
│   ├── src/types/      # Shared TypeScript types (cross-feature only)
│   └── src/constants/  # Frontend constants
├── backend/            # FastAPI app
│   ├── app/            # Main application package
│   │   ├── features/   # Feature folders (import/, clips/, export/, history/)
│   │   ├── core/       # Shared kernel: config, DB, middleware, base exceptions
│   │   ├── workers/    # Background task runners (pipeline stages)
│   │   └── utils/      # Shared utilities
│   ├── tests/          # pytest tests mirroring app/ structure
│   └── pyproject.toml  # uv project config
├── models/             # AI model files (gitignored, ~10GB)
├── media/              # originals/ and exports/ (gitignored)
├── docs/               # Specs, architecture docs
├── CLAUDE.md           # Project instructions for Claude Code
├── DESIGN.md           # Design system (palette, typography, spacing, components)
├── MEMORY.md           # Session memory (patterns, anti-patterns, discoveries)
└── docker-compose.yml  # MongoDB + optional services
```

## Context Boundaries

- **Frontend:** `frontend/src/` — React components, hooks, pages, client logic
- **Backend:** `backend/app/` — FastAPI routes, services, AI pipeline, video processing
- **Shared contracts:** TypeScript types in `frontend/src/types/` must mirror Pydantic models in `backend/app/models/`
- **Contract generation:** Backend Pydantic models are the source of truth. Use `pydantic-to-typescript` (or equivalent) to generate TypeScript interfaces — do not hand-write mirrored types. Run codegen after any Pydantic model change.
- **Never cross:** Frontend never imports from backend or vice versa. Communication via HTTP/WebSocket only.

## Design System

- **Source of truth:** `DESIGN.md` (project root) — defines color palette, typography, spacing scale, component patterns, and interaction styles for the entire app
- **Established once:** Created during the first feature PRD using `/ui-ux-pro-max`. All subsequent features reference and conform to it.
- **Updates:** Design system changes require their own PRD cycle (treated as a feature). Never silently drift per module.
- **Enforcement:** Every frontend component must use design tokens (MUI theme variables) — no hardcoded colors, font sizes, or spacing values
- **Consistency check:** During Gate 2 (Tech Docs), verify that proposed UI components align with `DESIGN.md`. Flag deviations before implementation.

## Code Conventions

### Frontend (TypeScript/React)

- `'use client'` only for components requiring browser APIs, event handlers, or React state
- Semantic HTML always (`<button>` not `<div onClick>`)
- Server Components by default; Client Components only when necessary
- Server Actions for mutations; `/api` routes only for external webhooks
- SWR for client-side data fetching with proper error/loading states
- WebSocket via a single shared hook for real-time pipeline progress

### Backend (Python)

- Type hints on ALL functions, parameters, and return values
- Pydantic BaseModel for all API request/response schemas
- Pydantic Settings for configuration (env var validation at startup)
- `async def` for all route handlers and I/O-bound operations
- Dependency injection via FastAPI `Depends()` for DB sessions, services
- No bare `dict` at API boundaries — always a Pydantic model
- Internal helpers may use plain dicts when Pydantic adds no value
- Service layer pattern: routes → services → repositories/workers
- Raise `HTTPException` only in route handlers, never in services (services raise domain exceptions, routes translate)

### Both Runtimes

- No default parameter values in function signatures that drive logic (exception: React prop destructuring; Pydantic model fields with type-safe defaults are allowed)
- Functions under 30 lines (JSX/render functions can be longer if well-structured)
- No comments unless the WHY is non-obvious
- Conventional Commits: `feat:`, `fix:`, `chore:`, `refactor:`, `test:`, `docs:`
- Atomic commits — one logical change per commit

## Guardrails

### Code Quality

**Anti-slop rules (hard ban):**
- No wrapper functions that just call one other function
- No "just in case" error handling for impossible states
- No generic names: `handleClick`, `processData`, `utils.ts` catch-alls — name by domain intent
- No premature abstractions — three concrete usages before extracting a shared helper
- No dead code, unused imports, or commented-out blocks left in the tree
- No unnecessary type aliases (`type ID = string` when `string` is clear in context)
- No fake docstrings that restate the function signature in prose
- No emojis anywhere in source code, comments, logs, or UI copy. Propose to use SVG if icons is need on the UI

**Comment policy:**
- Default: no comments. Code should be self-explanatory through naming and structure.
- Allowed: brief WHY comments when behavior would surprise a reader (workarounds, constraints, non-obvious decisions)
- Allowed: section markers in longer files (`// --- Transcription helpers ---`) to aid navigation
- Allowed: signal processing, coordinate geometry, and FFmpeg filter expressions — brief inline explanation of the formula or approach is required
- Forbidden: comments that describe WHAT the code does, reference tickets/PRs, or explain the caller
- Style: one line max, lowercase, no period. Direct and contextual.

### Modularization

**Feature-folder isolation:**
- Each user-facing feature owns its own folder containing routes, services, schemas, and tests
- Backend: `backend/app/features/{import,clips,export,history}/`
- Frontend: `frontend/src/features/{import,clips,export,history}/`
- A feature folder is a self-contained unit — it can be deleted without breaking other features

**Shared kernel (cross-cutting only):**
- `backend/app/core/` — DB connection, config, middleware, base exceptions
- `frontend/src/lib/` — API client, WebSocket hook, shared UI primitives
- Shared kernel exposes typed interfaces. Features import from kernel, never from each other.

**Isolation rules:**
- Features NEVER import from other feature folders directly
- Cross-feature communication goes through the shared kernel (event bus, DB queries via repository interfaces)
- Each feature declares its own Pydantic models / TypeScript types — no shared "mega types" file
- Adding a new feature = new folder + register routes. Zero changes to existing feature code.
- If two features need the same logic, promote it to shared kernel only after 2+ concrete usages

**State management:**
- No global mutable singletons
- Backend state scoped to request lifecycle (FastAPI dependencies) or explicit service instances
- Frontend state scoped to feature-level context providers or SWR cache keys
- Cross-feature state (e.g., current video ID) lives in shared kernel, read-only to features

### Test-Driven Development

**Workflow: Red -> Green -> Refactor**
1. Write a failing test that describes the expected behavior
2. Write the minimum code to make it pass
3. Refactor while keeping tests green

**Scope:**
- TDD applies to: API endpoints, route handlers, services, utilities, React components, hooks, pipeline orchestration logic
- TDD exempt: AI model inference modules (transcription service internals, LLM scoring internals) — these use pre-recorded fixtures in integration tests instead
- When adding a new feature folder, the first file created is the test file

**Rules:**
- No production code without a corresponding test that motivated it
- Tests describe behavior, not implementation — test what it does, not how
- One assertion per test when possible (keeps failures informative)
- Test names read as specifications: `test_rejects_video_longer_than_4_hours`, not `test_validation`
- Frontend: Vitest for unit (red-green-refactor), Playwright for E2E (written after feature works)
- Backend: pytest for unit + integration (red-green-refactor), `@pytest.mark.slow` for fixture-based AI tests

## Database (MongoDB)

- **Frontend (Mongoose):** `.lean()` for read-only queries with strict projection. Define indexes in schema files.
- **Backend (Motor):** Async Motor client. Define collections via Beanie ODM or raw Motor with Pydantic validation.
- Schema-level validation for required fields
- Never use raw `collection.` calls — always through model/repository layer
- Collections: `videos`, `clips`, `exports`

### Database Migrations

- MongoDB is schemaless but Mongoose/Beanie enforce shape at the app layer
- Schema changes follow a two-step deploy: (1) write code tolerant of both old and new shape, (2) run a migration script, (3) remove the compat shim
- Migration scripts live in `backend/app/core/migrations/` and are idempotent
- Never alter a collection shape in a route handler or service — migrations only

## API Design

- Response shape (both HTTP endpoints and WebSocket messages):
  ```json
  {
    "data": "T | null",
    "error": { "code": "MACHINE_READABLE", "message": "..." },
    "meta": {}
  }
  ```
- Error codes: machine-readable strings (`INVALID_INPUT`, `NOT_FOUND`, `PIPELINE_FAILED`)
- HTTP status codes: 200, 201, 400, 401, 404, 422 (validation), 500
- WebSocket progress messages: `{ "type": "progress", "stage": "...", "percent": N }`

## Environment Variables

- Frontend: prefix with `NEXT_PUBLIC_` (browser-accessible)
- Backend: no prefix, validated at startup via Pydantic Settings
- Never log or commit `.env` files
- Required vars documented in `.env.example` with placeholder values
- Key vars: `MONGODB_URI`, `MODELS_DIR`, `MEDIA_DIR`, `WHISPER_MODEL`, `LLAMA_MODEL`, `CUDA_VISIBLE_DEVICES`

## GPU & VRAM Management

- **Total budget:** 8GB VRAM (RTX 2000 Ada) — ~7.0–7.2GB usable after Windows 11 desktop overhead
- **Whisper medium:** ~2GB VRAM (CTranslate2 float16)
- **Llama 3.1 8B Q5_K_M:** ~5.5GB VRAM (llama-cpp-python, n_gpu_layers=auto)
- **Reserved:** ~0.5GB for CUDA overhead and FFmpeg hardware decode; Windows OS desktop consumes an additional ~0.8–1.0GB
- **Rules:**
  - The "never load both" rule is a **hard enforced lock** — not a guideline. The pipeline coordinator must assert free VRAM via `pynvml` before loading each model and abort if the allocation would exceed 7.0GB
  - Whisper loads first (transcription), then Llama loads for analysis
  - Models stay loaded across jobs within same session (avoid reload overhead)
  - If VRAM pressure detected, unload Whisper before loading Llama (sequential pipeline)
  - Whisper int8 quantization is the preferred fallback if VRAM pressure is detected at load time
  - Export stage (FFmpeg/OpenCV) runs CPU-bound; a new job's Stage 1 (Transcription) MAY begin while a prior job is in Stage 3 (Export), provided the coordinator verifies VRAM availability first
  - Monitor via `nvidia-smi` or pynvml — fail fast if allocation would exceed budget
- **RAM offload:** System has 64GB RAM. Llama layers can offload to CPU RAM if needed (slower but safe).

## AI Pipeline Architecture

- **Stage 1 — Transcription:** faster-whisper medium → word-level timestamps + confidence scores
- **Stage 2 — Analysis:** Llama 3.1 8B → viral candidate scoring (Hook 30%, Emotion 25%, Standalone 20%, Curiosity 15%, Rewatch 10%)
- **Stage 3 — Export:** FFmpeg extract → OpenCV smart crop (face/motion) → Whisper large-v3 re-transcribe clip → animate captions → burn-in → MP4
- Each stage is a separate service class, independently testable
- Pipeline orchestrated by a coordinator service that manages stage transitions and WebSocket progress updates

## Testing Strategy

### Frontend (Vitest + Playwright)

- 80% coverage on new files
- Unit test components, hooks, and utilities with Vitest
- E2E: Playwright for full workflows (upload → process → export)
- Mock WebSocket connections in unit tests, real connections in E2E

### Backend (pytest)

- Focus on integration tests: API endpoints hit real MongoDB (test DB)
- Unit tests for pure utility functions (timestamp math, scoring normalization)
- Do NOT mock AI model inference in tests — skip slow tests with `@pytest.mark.slow`
- Test pipeline stages with pre-recorded fixtures (sample audio/video segments)
- No coverage gate on AI service modules (model-dependent, hardware-dependent)

### E2E (Playwright)

- Cover golden path: import video → transcribe → select clip → export
- Run against both frontend dev server + backend dev server simultaneously

## Operational Concerns

### Structured Logging

- All backend log output is structured JSON (use `structlog` or Python `logging` with JSON formatter)
- Log files written to `media/logs/` with daily rotation
- Required fields per log entry: `timestamp`, `level`, `stage`, `job_id`, `message`
- Never use `print()` for diagnostic output — always the logger

### Job Resumption

- Each pipeline stage persists its output to MongoDB before the next stage starts
- On restart, the coordinator checks the last completed stage and resumes from there
- Stages are idempotent: re-running a completed stage is safe and returns cached output
- OOM or driver reset mid-stage marks the job `status: interrupted` — not `failed` — so the user can retry from the checkpoint

### Media Purge Policy

- `media/originals/` files are retained until the user explicitly deletes the video record
- `media/exports/` files older than 30 days with no recent access are eligible for auto-purge
- Purge is opt-in and triggered manually or via a scheduled task — never automatic without user confirmation
- The UI must display file sizes alongside video records so users can manage storage proactively

## Commands

Always prefix commands with `rtk` to minimize token usage. RTK passes through unchanged if no dedicated filter exists.

### Frontend

```bash
cd frontend && rtk pnpm dev          # Start Next.js dev server
cd frontend && rtk pnpm build        # Production build (87% savings)
cd frontend && rtk lint              # ESLint (84% savings)
cd frontend && rtk vitest run        # Vitest unit tests (99% savings)
cd frontend && rtk playwright test   # Playwright E2E (94% savings)
```

### Backend

```bash
cd backend && uv run uvicorn app.main:app --reload       # Start FastAPI dev server (no rtk, long-running)
cd backend && rtk test uv run pytest                     # Run tests (90% savings)
cd backend && rtk test uv run pytest -m "not slow"       # Skip AI model tests
cd backend && rtk uv run ruff check .                    # Lint
cd backend && rtk uv run ruff format .                   # Format
cd backend && rtk uv run mypy app/                       # Type check
cd backend && uv run python -m scripts.generate_ts       # Generate TS types from Pydantic models
```

### Infrastructure

```bash
rtk docker compose up -d mongodb     # Start local MongoDB
```

### Git (always use rtk)

```bash
rtk git status
rtk git diff
rtk git log
rtk git add <files> && rtk git commit -m "msg"
rtk git push
```

Models: Download manually to `models/` per README instructions.

## Git & Branching

- Branch naming: `type/short-description` (e.g., `feat/whisper-pipeline`, `fix/vram-overflow`)
- Never commit to main directly — feature branches + PRs
- Propose draft commit message before committing
- Large model files, `media/exports/`, and `.env` files are always gitignored

## Session Memory

### Writing Memory (end of every session)

After completing implementation (or when a session ends mid-work), append an entry to `MEMORY.md` (newest-first):

```markdown
## [YYYY-MM-DD] Feature/Task Name

### Implementation Log
- **PRD:** `docs/features/[name]/[name]-prd.md` — status: approved/in-progress
- **Tech Docs:** `docs/features/[name]/[name]-technical-docs.md` — status: approved/in-progress
- **Implementation:** status: complete/partial (describe what's done, what remains)

### Patterns (what worked well)
- [Reusable approach or technique worth repeating]

### Anti-Patterns (what to avoid)
- [Mistake made, dead end hit, or approach that wasted time]

### Discoveries (unexpected findings)
- [Gotchas, undocumented behavior, performance insights, dependency quirks]
```

Keep each entry concise — bullet points, not paragraphs.

### Reading Memory

- **Session start:** Read `MEMORY.md` before any work begins
- **Before Gate 1:** Re-read memory before drafting a new PRD to apply learned patterns and avoid repeated mistakes
