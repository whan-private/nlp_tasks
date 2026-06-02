import asyncio
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SSEEvent:
    """SSE 事件"""
    event: str
    data: dict[str, Any]


class SSEManager:
    """SSE 事件管理器 — 每个游戏实例一个，管理事件广播。"""

    # 用于通知消费者连接关闭的哨兵值
    CLOSE_SENTINEL = object()

    def __init__(self):
        # game_id → 该游戏的待发送事件队列列表
        self._queues: dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, game_id: str) -> asyncio.Queue:
        """订阅某个游戏的事件流，返回消费者队列。"""
        q: asyncio.Queue = asyncio.Queue()
        if game_id not in self._queues:
            self._queues[game_id] = []
        self._queues[game_id].append(q)
        return q

    def unsubscribe(self, game_id: str, queue: asyncio.Queue):
        """取消订阅。"""
        if game_id in self._queues:
            self._queues[game_id] = [q for q in self._queues[game_id] if q is not queue]

    async def emit(self, game_id: str, event: str, data: dict[str, Any]):
        """向指定游戏的所有订阅者广播事件。"""
        sse_event = SSEEvent(event=event, data=data)
        queues = self._queues.get(game_id, [])
        dead_queues = []
        for q in queues:
            try:
                q.put_nowait(sse_event)
            except asyncio.QueueFull:
                dead_queues.append(q)
        # 清理已满的队列
        for q in dead_queues:
            queues.remove(q)

    def close_all(self, game_id: str):
        """向所有订阅者发送关闭哨兵并清理队列。"""
        queues = self._queues.pop(game_id, [])
        for q in queues:
            try:
                q.put_nowait(self.CLOSE_SENTINEL)
            except asyncio.QueueFull:
                pass

    def cleanup(self, game_id: str):
        """清理某个游戏的所有订阅（兼容旧接口，直接调用 close_all）。"""
        self.close_all(game_id)


# 全局单例
sse_manager = SSEManager()
