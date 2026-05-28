"""初始化数据库表 — 创建 games, players, actions, game_logs 四张表（含字段注释）

Revision ID: 001
Revises:
Create Date: 2026-05-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建所有表。"""

    # ---- games 游戏主表 ----
    op.create_table(
        "games",
        sa.Column("id", sa.String(32), primary_key=True,
                  comment="游戏唯一ID"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending",
                  comment="游戏状态: pending=等待中, playing=进行中, finished=已结束"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(),
                  comment="创建时间"),
        sa.Column("started_at", sa.DateTime, nullable=True,
                  comment="开始时间"),
        sa.Column("finished_at", sa.DateTime, nullable=True,
                  comment="结束时间"),
        sa.Column("winner", sa.String(16), nullable=True,
                  comment="获胜阵营: werewolf=狼人, villager=村民"),
        sa.Column("config", sa.JSON, nullable=True,
                  comment="游戏配置（角色分配、人数等）"),
    )

    # ---- players 玩家表 ----
    op.create_table(
        "players",
        sa.Column("id", sa.String(32), primary_key=True,
                  comment="玩家唯一ID"),
        sa.Column("game_id", sa.String(32), sa.ForeignKey("games.id"), nullable=False,
                  comment="所属游戏ID"),
        sa.Column("name", sa.String(64), nullable=False,
                  comment="玩家名称"),
        sa.Column("role", sa.String(16), nullable=False,
                  comment="角色: werewolf=狼人, seer=预言家, witch=女巫, hunter=猎人, villager=村民"),
        sa.Column("is_ai", sa.Boolean, nullable=False, server_default=sa.text("TRUE"),
                  comment="是否为AI玩家"),
        sa.Column("is_alive", sa.Boolean, nullable=False, server_default=sa.text("TRUE"),
                  comment="是否存活"),
        sa.Column("team", sa.String(16), nullable=False,
                  comment="所属阵营: werewolf=狼人阵营, villager=村民阵营"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(),
                  comment="创建时间"),
    )

    # ---- actions 行动记录表 ----
    op.create_table(
        "actions",
        sa.Column("id", sa.String(32), primary_key=True,
                  comment="行动唯一ID"),
        sa.Column("game_id", sa.String(32), sa.ForeignKey("games.id"), nullable=False,
                  comment="所属游戏ID"),
        sa.Column("round", sa.Integer, nullable=False,
                  comment="回合数"),
        sa.Column("phase", sa.String(8), nullable=False,
                  comment="游戏阶段: night=夜晚, day=白天"),
        sa.Column("actor_id", sa.String(32), sa.ForeignKey("players.id"), nullable=False,
                  comment="行动者玩家ID"),
        sa.Column("action_type", sa.String(16), nullable=False,
                  comment="行动类型: kill=狼人杀人, check=预言家查验, save=女巫救人, poison=女巫毒人, shoot=猎人开枪, vote=投票, speak=发言"),
        sa.Column("target_id", sa.String(32), sa.ForeignKey("players.id"), nullable=True,
                  comment="目标玩家ID"),
        sa.Column("content", sa.Text, nullable=True,
                  comment="发言内容或行动详情"),
        sa.Column("timestamp", sa.DateTime, server_default=sa.func.now(),
                  comment="行动时间"),
    )

    # ---- game_logs 游戏日志表 ----
    op.create_table(
        "game_logs",
        sa.Column("id", sa.String(32), primary_key=True,
                  comment="日志唯一ID"),
        sa.Column("game_id", sa.String(32), sa.ForeignKey("games.id"), nullable=False,
                  comment="所属游戏ID"),
        sa.Column("round", sa.Integer, nullable=False,
                  comment="回合数"),
        sa.Column("phase", sa.String(8), nullable=False,
                  comment="游戏阶段: night=夜晚, day=白天"),
        sa.Column("event", sa.String(32), nullable=False,
                  comment="事件类型: game_start, werewolf_kill, seer_check, witch_save, witch_poison, player_speak, vote_result, player_death, game_end 等"),
        sa.Column("data", sa.JSON, nullable=False,
                  comment="事件数据（JSON格式）"),
        sa.Column("visible_to", sa.JSON, nullable=True,
                  comment="可见玩家ID列表（None=所有玩家可见）"),
        sa.Column("timestamp", sa.DateTime, server_default=sa.func.now(),
                  comment="事件时间"),
    )


def downgrade() -> None:
    """删除所有表（按外键依赖逆序）。"""
    op.drop_table("game_logs")
    op.drop_table("actions")
    op.drop_table("players")
    op.drop_table("games")
