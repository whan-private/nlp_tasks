from app.agents.base_agent import BaseAgent, GameState, VisibleInfo
from app.services.role_system import Hunter


class HunterAgent(BaseAgent):
    """猎人 Agent — 死亡时开枪带走一名玩家。"""

    def perceive(self, game_state: GameState) -> VisibleInfo:
        info = VisibleInfo(
            player_id=self.player_id,
            role_name=self.role.name,
            team=self.role.team.value,
            round=game_state.round,
            phase=game_state.phase,
            alive_players=game_state.alive_players,
            dead_players=game_state.dead_players,
            extra={
                "can_shoot": self.role.can_shoot,
            },
        )
        return info

    def reason(self, visible_info: VisibleInfo) -> str:
        lines = [
            f"玩家 {self.player_id}（猎人）正在推理",
            f"当前回合: 第 {visible_info.round} 轮",
            f"当前阶段: {visible_info.phase}",
            f"存活玩家: {[p for p in visible_info.alive_players]}",
        ]
        if visible_info.extra.get("is_dying"):
            lines.append("你即将死亡！选择你认为最像狼人的玩家开枪带走")
        else:
            lines.append("策略：积极参与发言和投票，不畏惧被怀疑")
            lines.append("即使被投票出局也能开枪带走狼人")
        return "\n".join(lines)

    def decide(self, reasoning: str) -> dict:
        return {
            "reasoning": reasoning,
            "action": {"type": "shoot", "target_id": ""},
        }

    def speak(self, context: dict) -> str:
        return "我是一名村民，我觉得那个发言最可疑的人值得仔细分析。"

    def on_death(self) -> dict | None:
        if self.role.can_shoot:
            return {"type": "shoot", "target_id": ""}
        return None
