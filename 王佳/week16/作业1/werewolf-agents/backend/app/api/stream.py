import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.services.sse_service import sse_manager

router = APIRouter(prefix="/api/game", tags=["SSE 事件流"])


@router.get("/{game_id}/stream")
async def game_stream(game_id: str, request: Request):
    """订阅游戏实时事件流（SSE）。"""
    queue = sse_manager.subscribe(game_id)

    async def event_generator():
        try:
            # 立即发送连接成功事件，避免前端长时间等待
            yield {"event": "connected", "data": "{}"}
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    if event is sse_manager.CLOSE_SENTINEL:
                        break
                    yield {
                        "event": event.event,
                        "data": json.dumps(event.data, ensure_ascii=False),
                    }
                except asyncio.TimeoutError:
                    # 发送心跳保活
                    yield {"event": "heartbeat", "data": "{}"}
        finally:
            sse_manager.unsubscribe(game_id, queue)

    return EventSourceResponse(event_generator())
