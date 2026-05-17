from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core.ws.manager import ConnectionManager


def _make_ws(*, fail_on_send: bool = False) -> Any:
    ws = AsyncMock()
    sent: list[Any] = []

    async def send_json(payload: Any) -> None:
        if fail_on_send:
            raise RuntimeError("ws broken")
        sent.append(payload)

    ws.send_json = send_json
    ws.sent = sent
    return ws


async def test_subscribe_adds_connection_to_topic() -> None:
    mgr = ConnectionManager()
    ws = _make_ws()
    await mgr.subscribe("video-1", ws)
    assert mgr.subscriber_count("video-1") == 1


async def test_subscriber_count_is_zero_for_unknown_topic() -> None:
    mgr = ConnectionManager()
    assert mgr.subscriber_count("never-seen") == 0


async def test_broadcast_delivers_to_all_topic_subscribers() -> None:
    mgr = ConnectionManager()
    ws_a = _make_ws()
    ws_b = _make_ws()
    await mgr.subscribe("video-1", ws_a)
    await mgr.subscribe("video-1", ws_b)
    await mgr.broadcast("video-1", {"type": "progress", "percent": 42})
    assert ws_a.sent == [{"type": "progress", "percent": 42}]
    assert ws_b.sent == [{"type": "progress", "percent": 42}]


async def test_broadcast_to_unknown_topic_is_no_op() -> None:
    mgr = ConnectionManager()
    await mgr.broadcast("phantom", {"type": "progress"})


async def test_broadcast_does_not_leak_across_topics() -> None:
    mgr = ConnectionManager()
    ws_a = _make_ws()
    ws_b = _make_ws()
    await mgr.subscribe("video-1", ws_a)
    await mgr.subscribe("video-2", ws_b)
    await mgr.broadcast("video-1", {"type": "progress", "percent": 50})
    assert ws_a.sent == [{"type": "progress", "percent": 50}]
    assert ws_b.sent == []


async def test_failing_subscriber_is_removed_and_others_still_receive() -> None:
    mgr = ConnectionManager()
    healthy = _make_ws()
    broken = _make_ws(fail_on_send=True)
    await mgr.subscribe("video-1", healthy)
    await mgr.subscribe("video-1", broken)
    await mgr.broadcast("video-1", {"type": "progress", "percent": 1})
    assert healthy.sent == [{"type": "progress", "percent": 1}]
    assert mgr.subscriber_count("video-1") == 1


async def test_disconnect_removes_subscriber() -> None:
    mgr = ConnectionManager()
    ws = _make_ws()
    await mgr.subscribe("video-1", ws)
    await mgr.disconnect("video-1", ws)
    assert mgr.subscriber_count("video-1") == 0


async def test_disconnect_unknown_subscriber_does_not_raise() -> None:
    mgr = ConnectionManager()
    ws = _make_ws()
    await mgr.disconnect("video-1", ws)


async def test_subscribe_same_ws_twice_is_idempotent() -> None:
    mgr = ConnectionManager()
    ws = _make_ws()
    await mgr.subscribe("video-1", ws)
    await mgr.subscribe("video-1", ws)
    assert mgr.subscriber_count("video-1") == 1


async def test_module_level_singleton_exists() -> None:
    from app.core.ws import manager

    assert isinstance(manager.ws_manager, ConnectionManager)


@pytest.mark.parametrize("topic", ["video-a", "video-b", "video-c"])
async def test_topics_are_isolated(topic: str) -> None:
    mgr = ConnectionManager()
    ws = _make_ws()
    await mgr.subscribe(topic, ws)
    await mgr.broadcast(topic, {"hello": topic})
    assert ws.sent == [{"hello": topic}]
