from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.db.client import close_client, get_db
from app.core.db.health import ping as mongo_ping
from app.core.logging.setup import configure_logging, get_logger
from app.features.import_ import routes as import_routes
from app.features.import_.cleanup import (
    mark_stale_uploading_as_failed,
    sweep_stale_temp_files,
)
from app.features.import_.repository import VideoRepository

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings = get_settings()
    (settings.originals_dir / ".tmp").mkdir(parents=True, exist_ok=True)
    settings.thumbnails_dir.mkdir(parents=True, exist_ok=True)

    swept = sweep_stale_temp_files(settings.originals_dir)
    stale = await mark_stale_uploading_as_failed(VideoRepository(get_db()))
    logger.info(
        "startup",
        api_port=settings.api_port,
        mongodb_db=settings.mongodb_db,
        tmp_swept=swept,
        stale_uploads_failed=stale,
    )
    yield
    await close_client()
    logger.info("shutdown")


app = FastAPI(
    title="AI Clipper Backend",
    version="0.1.0",
    lifespan=lifespan,
)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(import_routes.router, prefix="/api")
app.include_router(import_routes.media_router)
import_routes.register_exception_handlers(app)

settings.thumbnails_dir.mkdir(parents=True, exist_ok=True)


@app.get("/health")
async def health() -> dict[str, object]:
    mongo_ok = await mongo_ping()
    return {
        "data": {
            "status": "ok" if mongo_ok else "degraded",
            "mongo": mongo_ok,
        },
        "error": None,
    }


@app.websocket("/ws/{job_id}")
async def websocket_placeholder(ws: WebSocket, job_id: str) -> None:
    await ws.accept()
    await ws.send_json({"type": "connected", "job_id": job_id})
    try:
        while True:
            msg = await ws.receive_text()
            await ws.send_json({"type": "echo", "job_id": job_id, "received": msg})
    except WebSocketDisconnect:
        logger.info("ws_disconnect", job_id=job_id)
