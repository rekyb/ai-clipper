# AI Clipper — Session Memory

Newest entries on top.

---

## [2026-05-17] Chunk 2B — Transcription Pipeline + WebSocket Progress

### Implementation Log
- **PRD:** `docs/features/transcription-pipeline/transcription-pipeline-prd.md` — approved
- **Tech Docs:** `docs/features/transcription-pipeline/transcription-pipeline-technical-docs.md` — approved
- **Verification:** `docs/features/transcription-pipeline/transcription-pipeline-verification.md` — Gate 3 approved
- **Implementation:** complete. 256 backend tests + 179 frontend tests, lint+mypy clean.
- **Status of branch `2b-transcription-pipeline-websocket-progress`:** ready for commit/merge; awaiting user authorization to commit.

### Patterns (worked well)
- **In-process asyncio worker in FastAPI lifespan + atomic `findOneAndUpdate` for FIFO claim.** Single-GPU pipelines don't need Celery/RQ — `asyncio.create_task(worker.run_forever())` started in lifespan, claim via `find_one_and_update({status: queued}, sort=createdAt)` is correct, simple, and crash-safe. Sweep-on-startup handles `transcribing`→`queued` for crashed processes.
- **Snapshot-on-subscribe WebSocket, no replay buffer.** `/ws/{video_id}` sends the current state when a client connects, then live events thereafter. Reconnect/refresh is trivially correct; no buffering, no replay protocol. Exponential backoff `[500, 1000, 2000, 5000, 10000]` on the client.
- **`asyncio.to_thread` + `run_coroutine_threadsafe` to bridge sync Whisper iterator to async loop.** faster-whisper's `transcribe()` returns a sync generator. Iterate it in a thread; for each segment, dispatch `on_segment(...)` back onto the main loop via `run_coroutine_threadsafe(coro, loop).result()`. Keeps the worker fully async without blocking.
- **Pydantic discriminated union via `Literal[type]` for WS event envelope.** `ProgressEvent(type: Literal["progress","complete","error"])` codegens to a clean TS discriminated union — frontend reducer pattern matches on `event.type` with full type narrowing.
- **Per-package try/except in CUDA DLL registrar.** One corrupt nvidia wheel shouldn't shadow the others. Each `import_module` + `add_dll_directory` wrapped independently with structured `log.warning("cuda_dll_dir_skipped", reason=...)`. Made the eventual `__file__ is None` bug self-diagnose from logs.

### Anti-Patterns (avoid)
- **Don't check `module.__file__` to find a wheel's data dir** — namespace packages (PEP 420) have `__file__ = None`. The `nvidia.cublas` / `nvidia.cuda_runtime` / `nvidia.cudnn` wheels install as namespace packages. Use `getattr(mod, "__path__", None)` (walks `_NamespacePath` entries) and fall back to `__file__.parent` only if `__path__` is absent. **Why:** the wrong check silently skipped DLL registration for exactly the wheels we needed.
- **`os.add_dll_directory` does NOT cover transitive DLL loads on Windows.** When `cublas64_12.dll` itself loads its dependency `cudart64_12.dll`, Windows uses the standard search order which does NOT consult Python's added directories — only `PATH`, the EXE dir, and system dirs. **Fix:** prepend each bin dir to `os.environ["PATH"]` alongside `add_dll_directory` (idempotent — check before prepending). **Symptom if you don't:** `WhisperModel(...)` constructor succeeds (top-level cuBLAS load works), but the first `transcribe()` call dies with `Library cublas64_12.dll is not found or cannot be loaded` when cuBLAS tries to lazy-load cuDART for the first GPU op.
- **`nvidia-cublas-cu12` does NOT bundle the CUDA runtime.** It depends on `nvidia-cuda-runtime-cu12` (cudart64_12.dll). Without it you get the same "library not found or cannot be loaded" error. Add all three: `nvidia-cuda-runtime-cu12`, `nvidia-cublas-cu12`, `nvidia-cudnn-cu12`.
- **Don't split `llama-cpp-python` into the same `--extra` as faster-whisper.** llama-cpp-python builds from source on Windows and needs MSVC + nmake. Split into `--extra whisper` (Phase 2) and `--extra llama` (Phase 3). For llama, pull from `https://abetlen.github.io/llama-cpp-python/whl/cu124` via `[tool.uv.sources]` + `[[tool.uv.index]]` to avoid the build entirely.
- **Mongo timestamps truncate to millisecond precision.** Tests asserting `before <= doc.timestamp <= after` flake when `before`/`after` are microsecond-precise Python timestamps. Add `timedelta(milliseconds=1)` slack to the bounds.
- **`pynvml` (deprecated) → `nvidia-ml-py`.** Same `import pynvml` API, no deprecation warning, actively maintained.
- **Default `CORS_ORIGINS=["http://localhost:3000"]` breaks when Next bounces to 3001** (port conflict). Either pin frontend to :3000 or extend `CORS_ORIGINS=http://localhost:3000,http://localhost:3001`. Backend logs an `OPTIONS /api/... 400` on preflight rejection — useful diagnostic signal.

### Discoveries (unexpected findings)
- **YouTube now requires cookies for many unauthenticated requests.** yt-dlp surfaces it as `Sign in to confirm you're not a bot. Use --cookies-from-browser or --cookies`. Note the apostrophe is **U+2019**, not ASCII — match both in error-mapping (`# noqa: RUF001` on the curly one). Added `YOUTUBE_COOKIES_FROM_BROWSER` (`chrome`, `firefox`, `edge`, with optional `:Profile 1`) and `YOUTUBE_COOKIES_FILE` settings; mapped to a new `VIDEO_AUTH_REQUIRED` error code.
- **`cookies-from-browser=chrome` is broken on Windows when Chrome is running.** Chrome 127+ uses app-bound encryption that blocks cookie reads while the process holds the DB. Either close Chrome first or use `firefox`/`edge` (no such restriction). For headless/automation, exported `cookies.txt` (Netscape format) via `YOUTUBE_COOKIES_FILE` is more reliable. **Always gitignore `cookies.txt`** — contains session tokens equivalent to a logged-in YouTube session.
- **fake test imports in Python: `dict.get(name, _RaiseImport(name))` evaluates the default eagerly.** This caused a confusing test failure where every `fake_import` call raised. Use an `if name in stubs: return stubs[name]; else: raise ImportError(name)` block instead.
- **Vitest fake-timers break `waitFor`** — `waitFor` polls on real time, so a `vi.useFakeTimers()` test waiting on a debounced/throttled event hangs. Use real timers by default; switch to fake only for the specific reconnect-backoff tests where you explicitly advance time.
- **CRLF on Windows breaks `^---\n.*\n---` frontmatter regexes.** Use `/^---\r?\n([\s\S]+?)\r?\n---/` in `tokens.test.ts`-style frontmatter parsers so the same regex works on both line endings.

---

## [2026-05-17] SonarCloud PR Hardening Pass

### Implementation Log
- **Trigger:** SonarCloud quality gate failed on PR #5 (Phase 2A merge to `main`) — ~20 annotations across 4 rounds, 2 failures + many warnings + 8 unreviewed security hotspots.
- **Fetched findings via `WebFetch` of `github.com/<owner>/<repo>/pull/<n>/checks?check_run_id=<id>`** — returns the annotation table directly (file, line, rule message, severity). Beats clicking through SonarCloud UI.
- **Round 1 (HTTPException 404 docs, sync `.open()` in async fn, `void` operator, eslint-disable without rules, sort without compare):** documented 404 in `responses=`, added `aiofiles` dep + switched `_stream_to_disk` to `async with aiofiles.open`, removed `void` operators in 3 places, post-processed pydantic2ts header in `scripts/generate_ts.py` with rule-specific disables, added `localeCompare` to sort calls.
- **Round 2 (async fn no async features, props not readonly, useless `{}`):** `close_client` → sync `def` (motor's `client.close()` is sync); `serve_thumbnail` → sync `def` (FastAPI threadpools sync handlers — fine for blocking I/O); wrapped 9 React components' inline prop types with `Readonly<...>`; dropped `?? {}` from `...init?.headers` (spreading `undefined` is a no-op).
- **Round 3 (10 issues incl. path injection, `Number.parseInt`, redundant Exception, async test mocks, etc.):** validated `generate_ts.py` paths with `.relative_to(REPO_ROOT)`; switched `_file_chunks` test helper to `aiofiles`; added `await asyncio.sleep(0)` to 5 protocol-implementing mock methods; dropped `json.JSONDecodeError` from `except (KeyError, ValueError, ...)` tuple (it's a `ValueError` subclass); `parseInt/parseFloat` → `Number.parseInt/parseFloat`; replaced `Array.from({length:6}).map((_, i) => key={i})` with a static `SKELETON_KEYS` array; `.replace(/\\/g, ...)` → `.replaceAll('\\', ...)`; `pytest.approx` for float `==`; removed unnecessary `as Response` in `test-utils.tsx`.
- **Round 4 (security: clear-text HTTP, action pinning):** pinned all 5 GitHub Actions to full commit SHAs with trailing `# vX.Y.Z` Dependabot-style comments; flipped `httpx.AsyncClient(base_url="http://test")` and CORS env test data to `https://...`.

### Patterns (worked well)
- **`WebFetch` on a check-run URL surfaces the full SonarCloud annotation table.** `https://github.com/<owner>/<repo>/pull/<n>/checks?check_run_id=<id>` → markdown table of (file, line, rule, severity). Single fetch beats N click-throughs and gives an actionable batch to fix.
- **`git ls-remote https://github.com/<owner>/<repo> refs/tags/<tag>` to resolve action SHAs.** No `gh` CLI required. Use the specific patch tag (`v4.2.2`) not the major (`v4`) so the comment line is honest. Trailing `# vX.Y.Z` is what Dependabot expects when it bumps.
- **For protocol-implementing async test mocks, add `await asyncio.sleep(0)`.** Genuine event-loop yield, mimics real async behavior, satisfies `S7503` without `# NOSONAR` clutter. Use this any time a mock must stay `async` to match an interface.
- **Post-process auto-generated files in the generator script.** `pydantic2ts` emits `/* eslint-disable */` bare-banner that SonarQube flags; rather than editing the output (which regen overwrites), added `_rewrite_header()` to `scripts/generate_ts.py`. Same principle: never patch generator output by hand.
- **Path-injection (S2083) fix by `.relative_to(SAFE_ROOT)` validation.** Restructured `_rewrite_header` to take a relative string and reconstruct: `safe = (REPO_ROOT / output_rel).resolve(); safe.relative_to(REPO_ROOT.resolve())`. Raises if path escapes — proves to taint analyzer that no user-controlled input reaches the I/O sink.
- **Wrap component props with `Readonly<{...}>` inline** rather than extracting a `XxxProps` type. Keeps the prop list co-located with the function signature and reads naturally; satisfies `typescript:S6759` with minimal diff churn.

### Anti-Patterns (avoid)
- **Don't fix SonarQube symptoms blindly — read the rule message.** "Use https" on `http://test` is *not* an actual security fix; `http://test` is an opaque httpx-ASGI identifier never dialed. The flip is fine because tests still pass, but recognize when SonarQube is technically wrong (localhost dev defaults, SVG `xmlns`, `httpx` test base_urls) vs actually right (CI action `@v4` floating tags, sync I/O in async paths).
- **Don't claim "fixed" without `Grep` first when the user gives a rule message but no file path.** I almost guessed wrong on the http issue. Better to grep the codebase, list candidates, ask user which file. Earlier in this session I did exactly that and it saved a wrong-file edit.
- **Don't run `rtk test uv run pytest -m "not slow"`** — the rtk wrapper strips quotes around the marker expression and pytest sees `slow` as a file path. Either run `uv run pytest -m "not slow"` directly, or use a marker expression that doesn't need quoting.
- **Removing an import without grepping for in-file usages, take 2.** Recurred *again* in the `aiofiles` round (I added it, didn't remove anything this time — so OK). But the prior `PurePath` removal anti-pattern is real and worth its own line in the checklist below.

### Discoveries (unexpected)
- **SonarQube's `S5332` (clear-text HTTP) is overzealous on test fixtures and dev defaults.** Localhost is usually exempt, but `http://test` (httpx ASGI), `http://a.com` (CORS test data), and similar non-localhost test strings get flagged. SVG `xmlns="http://www.w3.org/2000/svg"` is NOT flagged (namespace identifier). Decision tree: real prod URL → fix; localhost dev default → leave + mark "Safe" in SonarCloud UI; test fixture string → flip to https (zero behavioral impact).
- **`pnpm/action-setup@v4` resolves to `f40ffcd9...` (HEAD of v4 branch) but `v4.0.0` resolves to `0c17529a...`.** They differ. Pin to the specific tag (`v4.0.0` → `0c17529a...`) for reproducibility — Dependabot will update both lines together when there's a real new release.
- **`json.JSONDecodeError` IS a `ValueError` subclass** — including it in `except (KeyError, ValueError, json.JSONDecodeError)` is redundant. SonarQube `python:S5713` (or similar) catches this. Same trap with `IndexError` ⊂ `LookupError`, `TimeoutError` ⊂ `OSError` (in 3.10+), `FileNotFoundError` ⊂ `OSError`.
- **FastAPI accepts both `def` and `async def` route handlers.** Sync handlers run in the threadpool — actually *more correct* for blocking I/O (`pathlib`, `subprocess.run`, file existence checks). Don't force `async` on a handler that doesn't await anything just because "FastAPI is async". `serve_thumbnail` doing path checks is genuinely better as plain `def`.
- **Motor's `AsyncIOMotorClient.close()` is synchronous** despite being on an async client. So `close_client` doesn't need to be `async` — was only async because the lifespan context happened to `await` it. Pattern: check the underlying library's sync/async surface before declaring wrappers async.
- **`Number.parseInt`/`Number.parseFloat` are spec-identical to the globals,** just namespaced. The SonarQube rule `typescript:S7773` exists because the globals are reassignable in old environments. Trivial fix: pure replace.
- **`String.prototype.replaceAll(literalString, replacement)`** (no regex) is cleaner than `replace(/\\/g, ...)` for literal-string global replacements. Available since ES2021 — Node 16+ — safe everywhere we run.
- **`pytest.approx(180.5)` with default `rel=1e-6` tolerance** is the right call for float equality on values that round-trip through serialization. Use `abs=...` for very small numbers near zero where relative tolerance breaks down.
- **The check-run URL format `pull/<n>/checks?check_run_id=<id>`** is fetchable without auth via `WebFetch` for public repos. For private repos: `gh api repos/<owner>/<repo>/check-runs/<id>` is the equivalent but `gh` wasn't installed.

### Local pre-PR SonarQube checklist (add to muscle memory)
```bash
# After local linters pass, scan for the most common SonarQube traps:
# 1. parseInt/parseFloat globals
rg -n 'parseInt|parseFloat' frontend/src --type ts | grep -v Number.

# 2. http:// in non-localhost source
rg -n 'http://(?!localhost|test|127\.0\.0\.1)' --type ts --type py

# 3. floating /* eslint-disable */ with no rule names
rg -n '/\* eslint-disable \*/' frontend/src

# 4. Float == in tests
rg -n 'assert.*== [0-9]+\.[0-9]+' backend

# 5. Async functions without await/async-with/async-for/yield (Python)
uv run python -c "import ast, pathlib; [print(f'{p}:{n.lineno} {n.name}') for p in pathlib.Path('app').rglob('*.py') for n in ast.walk(ast.parse(p.read_text())) if isinstance(n, ast.AsyncFunctionDef) and not any(isinstance(s, (ast.Await, ast.AsyncWith, ast.AsyncFor)) for s in ast.walk(n)) and not any(isinstance(s, ast.Yield) for s in ast.walk(n))]"
```

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
