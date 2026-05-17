import asyncio
from collections import defaultdict
from typing import Any, Protocol

import structlog

log = structlog.get_logger("ws.manager")


class WebSocketLike(Protocol):
    async def send_json(self, data: Any) -> None: ...


class ConnectionManager:
    def __init__(self) -> None:
        self._topics: dict[str, set[WebSocketLike]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(self, topic: str, ws: WebSocketLike) -> None:
        async with self._lock:
            self._topics[topic].add(ws)

    async def disconnect(self, topic: str, ws: WebSocketLike) -> None:
        async with self._lock:
            subs = self._topics.get(topic)
            if subs is None:
                return
            subs.discard(ws)
            if not subs:
                self._topics.pop(topic, None)

    async def broadcast(self, topic: str, payload: Any) -> None:
        async with self._lock:
            subscribers = list(self._topics.get(topic, ()))
        if not subscribers:
            return
        failed: list[WebSocketLike] = []
        for ws in subscribers:
            try:
                await ws.send_json(payload)
            except Exception as exc:
                log.warning("ws_broadcast_failed", topic=topic, error=str(exc))
                failed.append(ws)
        if failed:
            async with self._lock:
                subs = self._topics.get(topic)
                if subs is not None:
                    for ws in failed:
                        subs.discard(ws)
                    if not subs:
                        self._topics.pop(topic, None)

    def subscriber_count(self, topic: str) -> int:
        return len(self._topics.get(topic, ()))


ws_manager = ConnectionManager()
