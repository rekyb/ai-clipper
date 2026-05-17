# AI Clipper — Session Memory

Newest entries on top.

---

## [2026-05-17] Phase 2A: Video Import Foundation

### Implementation Log
- **PRD:** `docs/features/video-import/video-import-prd.md` v1.1 — status: approved
- **Tech Docs:** `docs/features/video-import/video-import-technical-docs.md` v1.1 — status: approved
- **Implementation:** complete. 21/21 steps from tech doc §8 landed on branch `2a-video-import-foundation` across ~30 atomic commits. 133 backend tests + 131 frontend Vitest tests + 1 Playwright E2E spec. Verification report at `docs/features/video-import/video-import-verification.md` signed off by user.

### Patterns (worked well)
- **Two-pass gate flow:** Started with v1.0 PRD + Tech Doc, then user edited `CLAUDE.md` mid-session to add `/ui-ux-pro-max` Gate 1 requirement + `DESIGN.md` artifact. Re-reading CLAUDE.md, diffing against current state, and reissuing v1.1 PRD/Tech Doc as targeted edits (not rewrites) caught the design-system gap without losing approved content.
- **Service signature with injected `chunks: AsyncIterator[bytes]`:** Kept the upload service decoupled from FastAPI's `UploadFile`. Routes adapt `UploadFile` → chunks; tests pass a real file's bytes via a tiny `_file_chunks(path)` helper. Real fixture videos + real ffmpeg + only the repo mocked = high-confidence tests with no extra plumbing.
- **Generate fixture videos on the fly with ffmpeg:** `_run_ffmpeg(["-f", "lavfi", "-i", "color=...", ...])` produces 5s mp4/mkv/audio-only fixtures session-scoped at ~1-2s per file. Zero binary blobs in the repo, deterministic, identical fixtures across dev + CI.
- **`tokens.test.ts` parses DESIGN.md frontmatter and asserts tokens.ts matches:** Any drift between the design system source-of-truth and the TS values fails a test immediately. Used `js-yaml` to parse the `---...---` block.
- **No-hex vitest guard (`no-hex.test.ts`):** Walks `src/`, fails on any `#[0-9a-fA-F]{3,8}` outside an allow-list. Cheaper than an ESLint plugin and catches every drift attempt.
- **`subprocess.run` inside `asyncio.to_thread`:** Decouples ffmpeg/ffprobe invocations from the event loop. Works under uvicorn's Windows Selector loop AND pytest's Proactor loop without per-platform branching.
- **camelCase wire format end-to-end:** Pydantic field aliases → `model_dump(by_alias=True)` in routes → `pydantic-to-typescript` codegen → TS interfaces with matching keys. Single source of truth, no hand-mirrored types.
- **`validation_alias` / `serialization_alias` split for `id`:** Pydantic accepts Mongo's `_id` on read, emits clean `id` on JSON dump. Both behaviors from one field declaration.
- **Lifespan crash-recovery sweep:** On startup, sweep stale `.tmp/` files and mark stuck `uploading` records as `failed` with `INTERRUPTED` code. Idempotent, runs every boot, no separate cron needed.
- **Promote shared utilities at the 3rd usage:** `surfaces.ts` lived in `features/import/lib/` for 2 consumers, moved to `lib/` when the AppBar became the 3rd. CLAUDE.md's "3 usages → shared kernel" rule mapped cleanly to the actual code shape.

### Anti-Patterns (avoid)
- **Tests passing on the default `ProactorEventLoop` but uvicorn forcing `WindowsSelectorEventLoopPolicy`:** `asyncio.create_subprocess_exec` raises `NotImplementedError` only under uvicorn's loop. Caught only by the user's manual smoke test. Mitigation: prefer `subprocess.run` + `asyncio.to_thread` for any subprocess work, or explicitly test under the uvicorn loop policy.
- **pydantic-settings v2 JSON-decodes list[str] env vars BEFORE field_validators run:** Phase 1's `cors_origins` env override was silently broken because the validator never ran. Fix: `Annotated[list[str], NoDecode]` on every list field. Test the env-override path, don't trust validator-only tests.
- **`size="small"` MUI TextField in a tall flex column:** A ~32 px input next to a 200 px dropzone reads as broken. Default MUI sizing (~56 px) + wrapping in a matching glass panel + same minHeight balances the layout.
- **Cross-key SWR optimistic update:** `cache.keys()` returns serialized strings while `mutate` takes `Arguments`. Bridging them added 30 lines of casting + a type error in TypeScript strict. Simpler revalidate-only delete shipped instead; tradeoff is a brief visual lag on delete.
- **`StatusFilterChips` exporting `StatusFilter` from index.tsx triggers eslint-config-next's barrel warnings:** Resolved by keeping the type export inline; if it grows, move types to `features/import/types.ts` after codegen runs.
- **Co-located feature tests need `testpaths` extension:** Phase 1 set `testpaths = ["tests"]` so pytest didn't auto-discover `app/features/*/tests/`. Solution: `testpaths = ["tests", "app/features"]` + matching ruff per-file-ignores pattern `"app/features/*/tests/**" = ["B"]`.
- **`mv` then `git add` separately doesn't trigger rename detection until both stages are added together:** Stage the old-path delete + new-path add in one `git add` call; git diff-stat then shows `rename`.
- **`scripts/init_db.py`'s `INDEXES: dict[..., dict[str, object]]`:** mypy can't spread `**dict[str, object]` into Motor's `create_index` overloads. Use `dict[str, Any]` for kwargs sinks.

### Discoveries (unexpected)
- **`pydantic2ts.generate_typescript_defs` shells out to `json2ts` (json-schema-to-typescript) via `npx`-style invocation.** Needed the package added to the frontend's devDependencies AND a Windows-aware path to `.bin/json2ts.cmd` because pydantic2ts can't auto-discover non-PATH binaries.
- **Auto-generated TS files (codegen header has `eslint-disable`) trigger the "Unused eslint-disable directive" warning** when the body has no lint issues to disable. Fix: add the file's glob to flat-config `globalIgnores`.
- **MUI v7 `<Stack alignItems="stretch">` doesn't propagate height to grandchildren unless every nested Box explicitly opts in.** Needed `height: '100%'` on outer wrappers + `flex: 1` on inner content boxes for the equal-height import columns.
- **Lucide React 1.16 is fine despite pre-1.0 history; provides better stroke control than `@mui/icons-material` (uses 1.5 px stroke by default, configurable per-icon).** Kept the existing MUI icons dep but new icons go via Lucide.
- **Playwright's `webServer: [...]` config can boot both backend + frontend with isolated DB + media dirs via env vars,** but `reuseExistingServer: !process.env.CI` makes local iteration 10x faster — the test reuses an already-running stack on the chosen ports.
- **yt-dlp 2026.3.17 maps age-gate errors as "Sign in to confirm your age. This video may be inappropriate"** — our `youtube._map_download_error` substring match `"confirm your age"` works; verified live on a real age-gated video during user smoke test.
- **MongoDB sparse + unique compound:** sparse means the index entry is omitted when the field is null/absent, so multiple `uploading` records (with `contentHash: null`) coexist without violating uniqueness. Documented in PRD § Story 5; tested in `test_content_hash_index_is_sparse_allowing_multiple_nulls`.
- **DESIGN.md's `surface-container` value `#201f21` is the spec value, but the Elevation section narrative mentions `#1E1E22`.** The frontmatter is authoritative per CLAUDE.md; the narrative drift is cosmetic but worth flagging if DESIGN.md ever gets a v2.

### Open items handed forward
- **Frontend E2E hasn't been run by me** — Playwright spec written and `--list` confirms discovery, but actual browser run is user-driven (boots a 2-server stack). User signed off Gate 3 based on backend + Vitest + manual demo.
- **Library search / pagination not in scope** — both deferred to Phase 6 per PRD. Library search across titles is a small lift (`?q=` + regex) if user wants it pre-Phase 6.
- **Phase 1 latent issues fixed in this chunk:** `cors_origins` env parsing, theme drift to Vivid Velocity, uvicorn Windows subprocess. If the README references Phase 1 limitations, those notes can be removed.
- **Pre-existing mypy warning in `app/core/logging/setup.py:32`** (`Returning Any from function declared to return BoundLogger`) is out of 2A scope but should be cleaned up next time anyone touches the logging kernel.

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
