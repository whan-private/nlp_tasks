"""Pytest 配置 & Fixtures — 为 API 测试提供 TestClient、测试数据库等。"""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db

# ---------- 测试数据库（SQLite 内存） ----------

TEST_DB_URL = "sqlite:///:memory:"

test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------- 模拟 LLM ----------

def _make_mock_openai():
    """创建一个完全 mock 的 AsyncOpenAI 实例。"""
    mock = MagicMock()
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock()]
    mock_completion.choices[0].message.content = '{"reasoning": "mock", "action": {"type": "speak", "content": "测试发言"}}'
    mock.chat.completions.create = AsyncMock(return_value=mock_completion)
    return mock


# ---------- Fixtures ----------

@pytest.fixture(scope="session")
def db_engine():
    """创建所有表，session 级别只执行一次。"""
    # 导入所有模型以注册到 Base.metadata
    from app.models.game import Game, Player  # noqa: F401
    from app.models.action import Action  # noqa: F401
    from app.models.log import GameLog  # noqa: F401

    Base.metadata.create_all(bind=test_engine)
    yield test_engine
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db(db_engine):
    """每个测试一个独立数据库会话（事务回滚）。"""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db):
    """FastAPI TestClient — 已注入测试数据库和 mock LLM。"""
    mock_llm = _make_mock_openai()

    with (
        patch("app.services.game_engine.AsyncOpenAI", return_value=mock_llm),
        patch("app.agents.summary_agent.AsyncOpenAI", return_value=mock_llm),
        patch("app.services.game_engine.get_settings"),
        patch("app.agents.summary_agent.get_settings"),
    ):
        from app.core.config import get_settings, Settings

        # 用测试配置覆盖
        test_settings = Settings(
            OPENAI_API_KEY="sk-test",
            OPENAI_MODEL="test-model",
            OPENAI_BASE_URL="https://test.api/v1",
            DATABASE_URL=TEST_DB_URL,
            DEBUG=False,
        )

        # 全局覆盖
        import app.core.config as config_mod
        original = config_mod.get_settings
        config_mod.get_settings = lambda: test_settings

        from app.main import app
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as tc:
            yield tc

        # 清理：停止所有活跃的游戏引擎
        from app.api.game import _active_games
        for engine in list(_active_games.values()):
            try:
                engine.stop()
            except Exception:
                pass
        _active_games.clear()

        app.dependency_overrides.clear()
        config_mod.get_settings = original
