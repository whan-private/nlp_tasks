import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uid() -> str:
    return uuid.uuid4().hex[:12]


class Game(Base):
    """游戏主表 — 记录每局游戏的状态与结果。"""
    __tablename__ = "games"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid,
                                    comment="游戏唯一ID")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending",
                                         comment="游戏状态: pending=等待中, playing=进行中, finished=已结束")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                  comment="创建时间")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True,
                                                         comment="开始时间")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True,
                                                          comment="结束时间")
    winner: Mapped[str | None] = mapped_column(String(16), nullable=True,
                                                comment="获胜阵营: werewolf=狼人, villager=村民")
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True,
                                                 comment="游戏配置（角色分配、人数等）")
    round: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                        comment="当前回合数")
    phase: Mapped[str | None] = mapped_column(String(16), nullable=True,
                                               comment="当前阶段: night / day")
    engine_state: Mapped[dict | None] = mapped_column(JSON, nullable=True,
                                                        comment="引擎完整状态快照，用于断点续玩")

    # 关联
    players: Mapped[list["Player"]] = relationship("Player", back_populates="game", cascade="all, delete-orphan")
    actions: Mapped[list["Action"]] = relationship("Action", back_populates="game", cascade="all, delete-orphan")
    logs: Mapped[list["GameLog"]] = relationship("GameLog", back_populates="game", cascade="all, delete-orphan")


class Player(Base):
    """玩家表 — 记录每局游戏中的玩家信息。"""
    __tablename__ = "players"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid,
                                    comment="玩家唯一ID")
    game_id: Mapped[str] = mapped_column(String(32), ForeignKey("games.id"), nullable=False,
                                          comment="所属游戏ID")
    name: Mapped[str] = mapped_column(String(64), nullable=False,
                                       comment="玩家名称")
    role: Mapped[str] = mapped_column(String(16), nullable=False,
                                       comment="角色: werewolf=狼人, seer=预言家, witch=女巫, hunter=猎人, villager=村民")
    is_ai: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True,
                                         comment="是否为AI玩家")
    is_alive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True,
                                            comment="是否存活")
    team: Mapped[str] = mapped_column(String(16), nullable=False,
                                       comment="所属阵营: werewolf=狼人阵营, villager=村民阵营")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                  comment="创建时间")

    # 关联
    game: Mapped["Game"] = relationship("Game", back_populates="players")
