# AI Clipper — Session Memory

Newest entries on top.

---

## [2026-05-17] GitHub Actions CI Setup

### Implementation Log
- **Workflow:** `.github/workflows/ci.yml` — two parallel jobs (`backend`, `frontend`) gated on PRs to `main` + pushes to `main`. Concurrency group cancels in-progress runs on new pushes.
- **backend job:** Ubuntu, MongoDB 7 service container, ffmpeg via apt, Python 3.12 via `astral-sh/setup-uv@v3` (cached on `backend/uv.lock`), `uv sync --no-install-project`, then `ruff format --check` → `ruff check` → `mypy app/` → `pytest -m "not slow"`.
- **frontend job:** Ubuntu, `pnpm/action-setup@v4` v11 (matches local), `actions/setup-node@v4` Node 22 (pnpm 11 requires Node ≥22.13 — uses `node:sqlite` builtin), pnpm-cache via setup-node, `pnpm install --frozen-lockfile` → `lint` → `vitest` → `next build`.
- **Excluded deliberately:** Playwright E2E (needs full backend + Mongo + ffmpeg + frontend simultaneously — too heavy/flaky for every PR), AI/video extras (`uv sync` without `--extra ai --extra video` keeps backend job under ~1 min), path filters (small project, branch protection semantics simpler with always-on jobs).
- **Branch protection:** user-configured in GitHub UI (Settings → Branches → ruleset on `main`, require `backend` + `frontend` checks).

### Patterns (worked well)
- **Mirror local tooling versions in CI exactly.** `pnpm --version` locally before pinning a version in the workflow. Lockfile compatibility ≠ runtime compatibility; the lockfile-producer version is what matters.
- **`uv sync --no-install-project` is fine** for this repo because `pyproject.toml` has `[tool.uv] package = false`; the project doesn't need installing as a package for lint/type/test runs. Saves seconds and avoids needing build deps in CI.
- **MongoDB service container with health check** + env vars (`MONGODB_URI`, `MONGODB_DB`) gives tests a real DB without any in-CI bootstrap script. `mongo:7` boots in ~5 s.
- **`concurrency.cancel-in-progress`** at workflow level. Saves CI minutes when pushing fixups rapidly during PR review.
- **Debug ruff isort categorization mismatches with `-v`.** `ruff check -v` prints `Categorized 'X' as Known(FirstParty) (SourceMatch("..."))` lines — pinpoints whether a file was found on disk vs treated as third-party. Saved 20 min of guessing.

### Anti-Patterns (avoid)
- **Did not run `ruff/mypy/pytest` locally before pushing the workflow.** Every CI failure today (`I001 download_models.py`, `no-any-return setup.py`, `F821 PurePath`, `test_sanitize_strips_path_components`, `test_generate_ts`) would have been caught by `cd backend && uv run ruff check . && uv run mypy app/ && uv run pytest -m "not slow"` before the first push. **Always** run the same commands CI runs locally before opening the PR.
- **Removed a symbol from imports without grepping for other usages.** Replaced `PurePath` with `PureWindowsPath` in the import line — `PurePath` was used in two other places in the same file. `Grep "PurePath"` in the file before deleting it would have flagged this in 2 seconds.
- **Pinned pnpm to v9 in CI without checking local version.** User had pnpm v11 locally. The `pnpm-workspace.yaml` used the v10+ `allowBuilds:` syntax which v9 silently ignores; v10+ also requires a `packages:` field which v9 doesn't. Mismatched version triggered both issues.
- **Pinned Node 20 without checking pnpm's Node-version requirement.** pnpm 11.1+ requires Node ≥22.13 (uses `node:sqlite`). Bump Node and pnpm together.
- **Made an edit, didn't re-run ruff, pushed → CI failed on the same file.** Faster to run the linter once locally than to wait for CI, read the error, and push again. The CI feedback loop is 2-5 min; local ruff is sub-second.

### Discoveries (unexpected)
- **`.gitignore: models/` was matching `backend/app/core/models/` source code** (the Phase 1 model loader stubs). Anchor with `/models/` when you mean repo-root only. Locally everything worked because the files existed on disk; CI got a different tree → ruff isort categorized `app.core.models.loader` as third-party (no source match), and `test_model_loader.py` would have failed pytest too once import resolution ran. The ruff I001 was the canary; the deeper bug was the un-tracked source. Lesson: **periodically run `git ls-files | wc -l` and sanity-check that all source modules are tracked.**
- **`pathlib.PurePath` is platform-dependent.** On Linux it does NOT recognize `\` as a path separator, so `PurePath("C:\\Windows\\evil.mp4").name` returns the whole string. Use `PureWindowsPath` for any filename-sanitization code path — it accepts both `/` and `\` on every host. This was a real security/UX bug: a Windows browser uploading via multipart can send Windows-style filenames to a Linux server, and the un-sanitized backslashes leaked path components into stored filenames.
- **ruff's isort first-party detection is disk-dependent unless explicitly configured.** Without `[tool.ruff.lint.isort] known-first-party = ["app"]`, ruff decides per-run based on which directories it can see. CI and local environments can disagree silently. **Always pin `known-first-party` for any non-installed-package layout.**
- **mypy strict + structlog:** `structlog.get_logger()` returns `Any` because the concrete type depends on `wrapper_class` configuration. Wrap with `cast(structlog.stdlib.BoundLogger, ...)` to satisfy `no-any-return`. Local `.mypy_cache` was masking this; CI's fresh run caught it. `rm -rf .mypy_cache && uv run mypy app/` before any "mypy is clean locally" claim.
- **pnpm v10+ requires `packages:` in `pnpm-workspace.yaml`.** Even for single-package projects. Use `packages: ['.']` to declare the current directory as the only workspace package; the `allowBuilds:` allowlist still works.
- **`generate_ts` test references `frontend/node_modules/.bin/json2ts`.** Backend CI job doesn't install frontend deps, so the test needs `@pytest.mark.skipif(not _JSON2TS.exists(), ...)`. Path check mirrors the script's own logic — skip is accurate (skips only when codegen actually can't run).
- **Git on Windows is converting LF→CRLF on every commit** (warnings: "LF will be replaced by CRLF the next time Git touches it"). Tolerable for now but could bite us later (especially Python `\r` in test fixtures, or shell scripts in `.github/workflows/`). Consider adding `.gitattributes` with `* text=auto eol=lf` and `*.py text eol=lf` next time we touch repo-wide config.

### Local pre-push checklist (add to your muscle memory)
```bash
# backend
cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy app/ && uv run pytest -m "not slow"
# frontend
cd frontend && pnpm lint && pnpm test && pnpm build
```
Run both before every push to a PR'd branch. Mirrors what CI does — if these pass, CI will (modulo platform-specific bugs the above session uncovered).

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
