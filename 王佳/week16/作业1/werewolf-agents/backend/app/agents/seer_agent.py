from app.agents.base_agent import BaseAgent, GameState, VisibleInfo
from app.services.role_system import Seer


class SeerAgent(BaseAgent):
    """预言家 Agent — 夜间查验玩家身份，白天引导投票。"""

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
                "action": "check",
                "check_results_visible": True,
            },
        )
        return info

    def reason(self, visible_info: VisibleInfo) -> str:
        lines = [
            f"玩家 {self.player_id}（预言家）正在推理",
            f"当前回合: 第 {visible_info.round} 轮",
            f"当前阶段: {visible_info.phase}",
            f"存活玩家: {[p for p in visible_info.alive_players]}",
        ]
        if visible_info.phase == "night":
            lines.append("夜间策略：查验可疑玩家的真实阵营")
            lines.append("优先查验发言最少或最可疑的玩家")
            if visible_info.extra.get("check_results"):
                lines.append(f"已有查验结果: {visible_info.extra['check_results']}")
        else:
            lines.append("白天策略：根据查验结果引导投票")
            lines.append("如果有查到狼人，考虑是否跳身份公布结果")
        return "\n".join(lines)

    def decide(self, reasoning: str) -> dict:
        return {
            "reasoning": reasoning,
            "action": {"type": "check", "target_id": ""},
        }

    def speak(self, context: dict) -> str:
        return "我注意到一些玩家的发言存在矛盾，需要更多信息来判断。"
