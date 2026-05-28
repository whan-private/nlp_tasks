import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uid() -> str:
    return uuid.uuid4().hex[:12]


class Action(Base):
    """行动表 — 记录玩家在游戏中的每次行动。"""
    __tablename__ = "actions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid,
                                    comment="行动唯一ID")
    game_id: Mapped[str] = mapped_column(String(32), ForeignKey("games.id"), nullable=False,
                                          comment="所属游戏ID")
    round: Mapped[int] = mapped_column(Integer, nullable=False,
                                        comment="回合数")
    phase: Mapped[str] = mapped_column(String(8), nullable=False,
                                        comment="游戏阶段: night=夜晚, day=白天")
    actor_id: Mapped[str] = mapped_column(String(32), ForeignKey("players.id"), nullable=False,
                                           comment="行动者玩家ID")
    action_type: Mapped[str] = mapped_column(String(16), nullable=False,
                                              comment="行动类型: kill=狼人杀人, check=预言家查验, save=女巫救人, poison=女巫毒人, shoot=猎人开枪, vote=投票, speak=发言")
    target_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("players.id"), nullable=True,
                                                   comment="目标玩家ID")
    content: Mapped[str | None] = mapped_column(Text, nullable=True,
                                                 comment="发言内容或行动详情")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                 comment="行动时间")

    # 关联
    game: Mapped["Game"] = relationship("Game", back_populates="actions")
    actor: Mapped["Player"] = relationship("Player", foreign_keys=[actor_id])
    target: Mapped["Player | None"] = relationship("Player", foreign_keys=[target_id])
