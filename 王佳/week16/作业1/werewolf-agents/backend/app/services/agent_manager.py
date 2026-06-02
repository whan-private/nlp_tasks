from dataclasses import dataclass
from typing import Any

from app.agents.base_agent import BaseAgent
from app.services.role_system import Team, create_role


@dataclass
class AgentContext:
    """Agent 上下文：包含角色实例和所属游戏。"""
    player_id: str
    role_name: str
    team: Team
    role: Any  # BaseRole 实例
    agent: BaseAgent | None = None


class AgentManager:
    """Agent 管理器 — 负责 Agent 的创建、信息隔离和行动协调。"""

    def __init__(self, game_id: str):
        self.game_id = game_id
        self.agents: dict[str, AgentContext] = {}

    def create_agents(self, player_roles: dict[str, str]) -> list[AgentContext]:
        """根据玩家角色映射创建 Agent 列表。

        Args:
            player_roles: {player_id: role_name}
        """
        contexts = []
        for player_id, role_name in player_roles.items():
            role = create_role(role_name)
            ctx = AgentContext(
                player_id=player_id,
                role_name=role_name,
                team=role.team,
                role=role,
            )
            self.agents[player_id] = ctx
            contexts.append(ctx)
        return contexts

    def get_agent(self, player_id: str) -> AgentContext | None:
        return self.agents.get(player_id)

    def get_alive_agents(self) -> list[AgentContext]:
        """获取所有存活 Agent 的上下文。"""
        return [ctx for ctx in self.agents.values()]

    def get_agents_by_role(self, role_name: str) -> list[AgentContext]:
        return [ctx for ctx in self.agents.values() if ctx.role_name == role_name]

    def get_agents_by_team(self, team: Team) -> list[AgentContext]:
        return [ctx for ctx in self.agents.values() if ctx.team == team]

    def mark_dead(self, player_id: str):
        """标记玩家死亡。"""
        if player_id in self.agents and self.agents[player_id].agent:
            self.agents[player_id].agent.is_alive = False

    def build_visible_info(self, player_id: str, game_state: dict) -> dict:
        """根据角色权限构建可见信息（信息隔离）。

        Args:
            player_id: 当前玩家 ID
            game_state: 完整游戏状态字典

        Returns:
            该玩家可见的信息子集
        """
        ctx = self.agents.get(player_id)
        if not ctx:
            return game_state

        role_name = ctx.role_name
        visible = {
            "player_id": player_id,
            "role_name": role_name,
            "team": ctx.team.value,
            "round": game_state.get("round", 0),
            "phase": game_state.get("phase", ""),
            "alive_players": game_state.get("alive_players", []),
            "dead_players": game_state.get("dead_players", []),
            "public_logs": game_state.get("public_logs", []),
            "extra": {},
        }

        # ---- 狼人阵营专属信息 ----
        if role_name == "werewolf":
            visible["extra"]["teammates"] = [
                ctx.player_id
                for ctx in self.get_agents_by_role("werewolf")
                if ctx.player_id != player_id
            ]
            visible["extra"]["night_discussion"] = game_state.get("werewolf_discussion", [])

        # ---- 预言家专属信息 ----
        elif role_name == "seer":
            visible["extra"]["check_results"] = game_state.get("seer_checks", {})

        # ---- 女巫专属信息 ----
        elif role_name == "witch":
            visible["extra"]["antidote_available"] = ctx.role.can_save()
            visible["extra"]["poison_available"] = ctx.role.can_poison()
            visible["extra"]["night_kill_target"] = game_state.get("night_kill_target")

        # ---- 猎人专属信息 ----
        elif role_name == "hunter":
            visible["extra"]["can_shoot"] = ctx.role.can_shoot

        return visible

    def get_werewolf_teammates(self, player_id: str) -> list[str]:
        """获取狼队友的 ID 列表（仅在玩家本身是狼人时返回）。"""
        ctx = self.agents.get(player_id)
        if not ctx or ctx.role_name != "werewolf":
            return []
        return [
            c.player_id
            for c in self.get_agents_by_role("werewolf")
            if c.player_id != player_id
        ]

    def get_team_mates(self, player_id: str) -> list[str]:
        """获取同阵营其他玩家的 ID 列表（不包含自己）。"""
        ctx = self.agents.get(player_id)
        if not ctx:
            return []
        return [
            c.player_id
            for c in self.get_agents_by_team(ctx.team)
            if c.player_id != player_id
        ]
