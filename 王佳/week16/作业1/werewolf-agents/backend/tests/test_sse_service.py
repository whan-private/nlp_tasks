"""SSE 服务测试。"""

import asyncio

import pytest

from app.services.sse_service import SSEManager, SSEEvent


class TestSSEEvent:
    def test_sse_event_creation(self):
        event = SSEEvent(event="test_event", data={"key": "value"})
        assert event.event == "test_event"
        assert event.data == {"key": "value"}


class TestSSEManager:
    """SSEManager 订阅/广播/取消测试。"""

    @pytest.fixture
    def mgr(self):
        manager = SSEManager()
        yield manager
        for gid in list(manager._queues.keys()):
            manager.cleanup(gid)

    # ---- 订阅 ----

    def test_subscribe_returns_queue(self, mgr):
        q = mgr.subscribe("game_1")
        assert q is not None
        assert q.empty()

    def test_subscribe_same_game_multiple_queues(self, mgr):
        q1 = mgr.subscribe("game_1")
        q2 = mgr.subscribe("game_1")
        assert q1 is not q2
        assert len(mgr._queues["game_1"]) == 2

    def test_subscribe_different_games(self, mgr):
        mgr.subscribe("game_1")
        mgr.subscribe("game_2")
        assert "game_1" in mgr._queues
        assert "game_2" in mgr._queues

    # ---- 广播 ----

    def test_emit_to_single_subscriber(self, mgr):
        q = mgr.subscribe("game_1")
        asyncio.run(mgr.emit("game_1", "event_a", {"msg": "hello"}))
        assert not q.empty()
        event = q.get_nowait()
        assert event.event == "event_a"
        assert event.data == {"msg": "hello"}

    def test_emit_to_multiple_subscribers(self, mgr):
        q1 = mgr.subscribe("game_1")
        q2 = mgr.subscribe("game_1")
        asyncio.run(mgr.emit("game_1", "round_start", {"round": 1}))
        assert not q1.empty()
        assert not q2.empty()
        e1 = q1.get_nowait()
        e2 = q2.get_nowait()
        assert e1.event == "round_start"
        assert e2.event == "round_start"

    def test_emit_game_isolation(self, mgr):
        """广播只发给目标游戏，不影响其他游戏。"""
        q1 = mgr.subscribe("game_1")
        q2 = mgr.subscribe("game_2")
        asyncio.run(mgr.emit("game_1", "event_1", {}))
        assert not q1.empty()
        assert q2.empty()

    def test_emit_nonexistent_game_no_error(self, mgr):
        """向不存在的游戏广播不应抛异常。"""
        try:
            asyncio.run(mgr.emit("nonexistent", "event", {}))
        except Exception as e:
            pytest.fail(f"emit 不应抛出异常: {e}")

    # ---- 取消订阅 ----

    def test_unsubscribe_removes_queue(self, mgr):
        q = mgr.subscribe("game_1")
        mgr.unsubscribe("game_1", q)
        asyncio.run(mgr.emit("game_1", "event", {}))
        assert q.empty()

    def test_unsubscribe_one_of_many(self, mgr):
        q1 = mgr.subscribe("game_1")
        q2 = mgr.subscribe("game_1")
        mgr.unsubscribe("game_1", q1)
        asyncio.run(mgr.emit("game_1", "event", {}))
        assert q1.empty()
        assert not q2.empty()

    # ---- 清理 ----

    def test_cleanup_removes_game(self, mgr):
        mgr.subscribe("game_1")
        assert "game_1" in mgr._queues
        mgr.cleanup("game_1")
        assert "game_1" not in mgr._queues

    def test_cleanup_nonexistent_no_error(self, mgr):
        try:
            mgr.cleanup("nonexistent")
        except Exception as e:
            pytest.fail(f"cleanup 不应抛出异常: {e}")

    # ---- 多次事件 ----

    def test_multiple_events_in_order(self, mgr):
        q = mgr.subscribe("game_1")
        asyncio.run(mgr.emit("game_1", "e1", {"n": 1}))
        asyncio.run(mgr.emit("game_1", "e2", {"n": 2}))
        asyncio.run(mgr.emit("game_1", "e3", {"n": 3}))
        assert q.qsize() == 3
        assert q.get_nowait().data == {"n": 1}
        assert q.get_nowait().data == {"n": 2}
        assert q.get_nowait().data == {"n": 3}
