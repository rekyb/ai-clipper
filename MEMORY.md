# AI Clipper — Session Memory

Newest entries on top.

---

## [2026-05-17] Phase 1: Foundation

### Implementation Log
- **PRD:** skipped — `docs/execution-plan.html` is treated as the master spec for foundational scaffolding. User explicitly approved this in chat.
- **Tech Docs:** skipped (same reason).
- **Implementation:** complete. Phase 1 deliverables shipped: backend + frontend skeletons, MongoDB up, model loader contracts, download scripts.

### Phase 1 verification (passed)
- Backend boots: `uvicorn app.main:app` -> `GET /health` returns `{"data":{"status":"ok","mongo":true},"error":null}`.
- WebSocket `/ws/{job_id}` accepts a connection, sends `connected` hello, echoes inbound messages.
- MongoDB: 3 collections (`videos`, `clips`, `exports`) + 10 indexes verified via `mongosh`.
- Frontend builds (Next 16.2.6) and dev server serves MUI-themed home page with our copy.
- Tests: 3/3 pytest (health + 2 model-loader missing-path tests), eslint clean, ruff clean.

### Patterns (worked well)
- `[project.optional-dependencies]` extras `ai` and `video` keep the dev `uv sync` light. Heavy CUDA deps install on demand with `uv sync --extra ai --extra video` before Phase 2.
- Backend feature-folder layout under `app/features/` + shared kernel under `app/core/` matches the CLAUDE.md guardrail and stays empty in Phase 1.
- structlog JSON output works out of the box — `configure_logging()` once in `lifespan`.
- `AppRouterCacheProvider` from `@mui/material-nextjs/v15-appRouter` works on Next 16 (the v15 import path stays stable since App Router API didn't break).
- API envelope `{data, error, meta?}` enforced in `lib/api.ts` and matched by FastAPI `/health` from day one — no contract drift waiting to bite.

### Anti-Patterns (avoid)
- `pnpm create next-app` aborts mid-install if `sharp` / `unrs-resolver` build scripts aren't approved. Approve them up front in `pnpm-workspace.yaml` with `allowBuilds: {sharp: true, unrs-resolver: true}` — don't trust the auto-generated placeholder text.
- `nohup ... &` in Bash dies when the shell session resets; verify pid actually survives with `tasklist` before relying on it. Same for PowerShell `Start-Job`.
- Docker Desktop install does NOT auto-start the engine on Windows — must launch `Docker Desktop.exe` (not just enable the service). Also adds its bin dir to system PATH but existing shell sessions retain stale PATH; reopen shell OR prepend `C:\Program Files\Docker\Docker\resources\bin` manually.
- Without `docker-credential-desktop` on PATH, even public-image pulls fail with `error getting credentials`.
- `Write` tool refuses to overwrite a file that wasn't `Read` first in this session — even for fresh writes after `uv init`. Read first, write second.

### Discoveries (unexpected)
- `pnpm create next-app@latest` now installs **Next 16**, not 15. API stable for our usage but worth flagging — README still says "Next.js 15".
- pnpm 11 uses `pnpm-workspace.yaml` for build-script approval (`allowBuilds` field), not the old `pnpm` block in `package.json`.
- `uv` auto-resolves Python 3.12 even when system Python is 3.14 — `requires-python = ">=3.12,<3.13"` in pyproject pins it correctly.
- PowerShell wraps native exe stderr lines as ErrorRecords; `$LASTEXITCODE` is the only reliable success signal. Treat the noisy stderr as cosmetic.
- MUI 7.3.11 + emotion 11.14 + Next 16 + React 19.2 all install with one peer warning (ignorable in Phase 1).
- The execution-plan.html VRAM budget didn't account for Windows desktop overhead (~0.8-1GB). CLAUDE.md guardrail captured this — pipeline coordinator must enforce a hard 7.0GB ceiling via pynvml, not the 8GB nameplate.

### Open items handed to Phase 2
- CUDA 12.x toolkit + cuDNN 9.x not installed yet. Required before `uv sync --extra ai`.
- ffmpeg is installed (`Gyan.FFmpeg` via winget) but not wired into any backend code yet.
- Model files not downloaded (~6.5GB). `scripts/download_models.py` is ready; user runs manually.
- README mentions Next.js 15 — update to "Next.js 16" when convenient.
