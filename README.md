# AI Clipper

Local-first AI video clipping tool. Identifies viral-worthy 30-60s segments from long-form videos and exports TikTok-ready clips with animated captions. Runs entirely on your machine — no cloud, no subscription.

## Hardware target

- **GPU:** NVIDIA RTX 2000 Ada (8GB VRAM) or comparable
- **RAM:** 64GB recommended (Llama 8B partial offload)
- **OS:** Windows 11 (developed against), Linux likely works
- **Disk:** ~15GB for models + workspace for media

## Stack

- **Frontend:** Next.js 16 (App Router) + TypeScript + MUI v7 + SWR
- **Backend:** FastAPI (Python 3.12) + Motor (MongoDB) + faster-whisper + llama-cpp-python
- **Database:** MongoDB 7 (via Docker Compose)
- **Models:** Whisper medium (always loaded), Llama 3.1 8B Q5_K_M (always loaded), Whisper large-v3 (lazy)

## Prerequisites

| Tool | Version | Install (Windows) |
|---|---|---|
| Docker Desktop | 25+ | `winget install Docker.DockerDesktop` |
| Node.js | 20+ | bundled with pnpm or `winget install OpenJS.NodeJS` |
| pnpm | 9+ | `npm install -g pnpm` |
| uv | 0.4+ | `winget install astral-sh.uv` |
| ffmpeg | 7+ | `winget install Gyan.FFmpeg` |
| CUDA Toolkit | 12.x | https://developer.nvidia.com/cuda-downloads |
| cuDNN | 9.x | https://developer.nvidia.com/cudnn |

CUDA + cuDNN are only required for Phase 2+ (AI inference). The Phase 1 scaffold runs without them.

After installing each tool, **open a new shell** so PATH picks it up. Docker Desktop also needs to be **launched once** so the engine starts.

## First-time setup

```powershell
# Clone, then from the repo root:

# 1. Start MongoDB (requires Docker Desktop running)
docker compose up -d mongodb

# 2. Install backend deps + create collections
cd backend
uv sync
uv run python -m scripts.init_db
cd ..

# 3. Install frontend deps
cd frontend
pnpm install
cd ..

# 4. (Optional, before Phase 2) Install AI dependencies
cd backend
uv sync --extra ai --extra video
cd ..
```

## Running the app

You need **three things running**: MongoDB, the backend, the frontend. Open three terminals.

### 1. MongoDB (any terminal)

```powershell
docker compose up -d mongodb     # idempotent — start or no-op
docker compose ps                # confirm "Up (healthy)"
```

### 2. Backend (terminal 2)

```powershell
cd backend
uv run uvicorn app.main:app --reload
```

Confirm:
- http://localhost:8000/health → `{"data":{"status":"ok","mongo":true},"error":null}`
- http://localhost:8000/docs → Swagger UI for all endpoints

Stop with `Ctrl+C`.

### 3. Frontend (terminal 3)

```powershell
cd frontend
pnpm dev
```

Open http://localhost:3000.

Stop with `Ctrl+C`.

## Models

Model weights are gitignored (~10GB combined). Download them with the provided scripts when you're ready to run Phase 2+:

```powershell
cd backend

# Whisper medium (~1.5GB) + Llama 3.1 8B Q5_K_M (~5GB)
uv run python -m scripts.download_models

# Whisper large-v3 (~3GB) — only needed for export-time caption precision (Phase 5)
uv run python -m scripts.download_whisper_large
```

Both scripts are idempotent — safe to re-run.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `docker: command not found` | Open a fresh PowerShell window so PATH picks up Docker, OR prepend `$env:PATH = "C:\Program Files\Docker\Docker\resources\bin;" + $env:PATH` |
| `error getting credentials - err: exec: "docker-credential-desktop"` | Same as above — Docker Desktop's bin dir isn't on the shell's PATH |
| `/health` returns `"mongo": false` | MongoDB container isn't running. Run `docker compose ps` to check, then `docker compose up -d mongodb` |
| Port 8000 already in use | `uv run uvicorn app.main:app --reload --port 8001` and set `NEXT_PUBLIC_API_URL=http://localhost:8001` in `frontend/.env.local` |
| Port 3000 already in use | `pnpm dev --port 3001` |
| `ModelNotInstalledError` from backend | Run the download scripts above, then restart the backend |

## Repo layout

```
ai-clipper/
├── frontend/            Next.js 16 app
│   └── src/
│       ├── app/         App Router pages
│       ├── components/  Shared UI (ComponentName/index.tsx)
│       ├── features/    Feature folders: import, clips, export, history
│       ├── hooks/       Shared hooks
│       └── lib/         API client, WS client, theme, env
├── backend/             FastAPI app
│   ├── app/
│   │   ├── core/        Shared kernel: config, db, logging, models
│   │   ├── features/    Feature folders (Phase 2+)
│   │   ├── workers/     Pipeline runners (Phase 2+)
│   │   └── main.py      FastAPI entrypoint
│   ├── scripts/         init_db, download_models, download_whisper_large
│   └── tests/           pytest suite
├── models/              AI model files (gitignored)
├── media/               originals/ and exports/ (gitignored)
├── docs/                Specs, PRDs, technical docs
├── docker-compose.yml   MongoDB service
└── README.md
```

## Development workflow

This project follows a gated workflow (PRD → Tech Docs → Implementation → Verification). See `CLAUDE.md` for the full convention.

## Useful commands

```powershell
# Backend
cd backend
uv run pytest                              # run all tests
uv run pytest -m "not slow"                # skip AI model tests
uv run ruff check . && uv run ruff format . # lint + format
uv run mypy app/                            # type check

# Frontend
cd frontend
pnpm lint                                  # eslint
pnpm build                                 # production build
pnpm vitest run                            # unit tests (Phase 2+)
pnpm playwright test                       # E2E tests (Phase 2+)
```
