import os
import sys
from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

# 将 backend 目录加入 sys.path，以便导入 app 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Alembic Config 对象
config = context.config

# 日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 导入所有模型，确保 Base.metadata 包含全部表
from app.core.database import Base
from app.models.game import Game, Player      # noqa: F401
from app.models.action import Action           # noqa: F401
from app.models.log import GameLog             # noqa: F401

target_metadata = Base.metadata

# 从应用配置读取数据库 URL（避免 .ini 文件中特殊字符的转义问题）
from app.core.config import get_settings
db_url = get_settings().DATABASE_URL


def run_migrations_offline() -> None:
    """离线模式迁移：生成 SQL 脚本而不连接数据库。"""
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式迁移：连接数据库并执行迁移。"""
    connectable = create_engine(db_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
