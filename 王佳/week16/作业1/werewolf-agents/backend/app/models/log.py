import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uid() -> str:
    return uuid.uuid4().hex[:12]


class GameLog(Base):
    """游戏日志表 — 记录游戏过程中的结构化事件，支持信息隔离。"""
    __tablename__ = "game_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid,
                                    comment="日志唯一ID")
    game_id: Mapped[str] = mapped_column(String(32), ForeignKey("games.id"), nullable=False,
                                          comment="所属游戏ID")
    round: Mapped[int] = mapped_column(Integer, nullable=False,
                                        comment="回合数")
    phase: Mapped[str] = mapped_column(String(8), nullable=False,
                                        comment="游戏阶段: night=夜晚, day=白天")
    event: Mapped[str] = mapped_column(String(32), nullable=False,
                                        comment="事件类型: game_start, werewolf_kill, seer_check, witch_save, witch_poison, player_speak, vote_result, player_death, game_end 等")
    data: Mapped[dict] = mapped_column(JSON, nullable=False,
                                        comment="事件数据（JSON格式）")
    visible_to: Mapped[list | None] = mapped_column(JSON, nullable=True,
                                                     comment="可见玩家ID列表（None=所有玩家可见）")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                 comment="事件时间")

    # 关联
    game: Mapped["Game"] = relationship("Game", back_populates="logs")
