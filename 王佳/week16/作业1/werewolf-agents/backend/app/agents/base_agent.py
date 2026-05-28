from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from app.services.role_system import BaseRole


@dataclass
class GameState:
    round: int
    phase: str
    alive_players: list
    dead_players: list
    actions: list = field(default_factory=list)
    logs: list = field(default_factory=list)


@dataclass
class VisibleInfo:
    """经过信息隔离过滤后的可见信息。"""
    player_id: str
    role_name: str
    team: str
    round: int
    phase: str
    alive_players: list
    dead_players: list
    extra: dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """Agent 基类 — 所有角色 Agent 继承此类实现 perceive → reason → decide → speak 决策链。"""

    def __init__(self, player_id: str, role: BaseRole):
        self.player_id = player_id
        self.role = role
        self.is_alive = True

    @abstractmethod
    def perceive(self, game_state: GameState) -> VisibleInfo:
        """感知阶段：从完整游戏状态提取角色可见信息（信息隔离）。"""
        ...

    @abstractmethod
    def reason(self, visible_info: VisibleInfo) -> str:
        """推理阶段：基于可见信息进行 CoT 推理。"""
        ...

    @abstractmethod
    def decide(self, reasoning: str) -> dict:
        """决策阶段：输出结构化动作。"""
        ...

    @abstractmethod
    def speak(self, context: dict) -> str:
        """发言阶段：生成自然语言发言内容。"""
        ...

    def on_death(self) -> Optional[dict]:
        """死亡回调（如猎人开枪）。返回额外动作或 None。"""
        return None
