import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import game, player, stream
from app.core.config import get_settings
from app.core.database import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    # 启动时校验关键配置
    if not settings.OPENAI_API_KEY:
        print(
            "\n"
            "  +--------------------------------------------------+\n"
            "  |  ERROR: OPENAI_API_KEY not configured            |\n"
            "  |                                                  |\n"
            "  |  Set in .env:                                    |\n"
            "  |  OPENAI_API_KEY=sk-xxx                           |\n"
            "  |  OPENAI_BASE_URL=https://dashscope.aliyuncs.com  |\n"
            "  |               /compatible-mode/v1                |\n"
            "  +--------------------------------------------------+\n"
        )
        sys.exit(1)
    print(f"  LLM: {settings.OPENAI_MODEL} @ {settings.OPENAI_BASE_URL}")

    # 启动时创建数据库表
    init_db()

    # 启动时清理卡住的游戏（服务器异常终止后，状态为 playing 的游戏没有对应引擎）
    from app.core.database import SessionLocal
    from app.models.game import Game as GameModel
    db = SessionLocal()
    try:
        stuck_count = db.query(GameModel).filter(GameModel.status == "playing").count()
        if stuck_count > 0:
            db.query(GameModel).filter(GameModel.status == "playing").update(
                {"status": "pending"}, synchronize_session=False
            )
            db.commit()
            print(f"  [启动清理] 已将 {stuck_count} 个卡住的游戏重置为 pending")
    finally:
        db.close()

    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(game.router)
app.include_router(player.router)
app.include_router(stream.router)


@app.get("/")
def root():
    return {"app": settings.APP_NAME, "version": "1.0.0", "status": "running"}


@app.get("/health")
def health():
    return {"status": "ok"}
