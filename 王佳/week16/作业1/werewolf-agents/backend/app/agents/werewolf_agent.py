from app.agents.base_agent import BaseAgent, GameState, VisibleInfo
from app.services.role_system import Werewolf


class WerewolfAgent(BaseAgent):
    """狼人 Agent — 夜间与队友合作击杀村民，白天伪装成村民。"""

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
                "action": "kill",
                "teammates_visible": True,
            },
        )
        return info

    def reason(self, visible_info: VisibleInfo) -> str:
        lines = [
            f"玩家 {self.player_id}（狼人）正在推理",
            f"当前回合: 第 {visible_info.round} 轮",
            f"当前阶段: {visible_info.phase}",
            f"存活玩家: {[p for p in visible_info.alive_players]}",
        ]
        if visible_info.phase == "night":
            lines.append("夜间策略：选择威胁最大的村民阵营玩家作为击杀目标")
            lines.append("考虑因素：是否有玩家跳预言家、发言是否有力、是否容易被怀疑")
        else:
            lines.append("白天策略：伪装成普通村民，隐藏狼人身份")
            lines.append("考虑因素：跟票还是主导投票、是否要牺牲队友")
        return "\n".join(lines)

    def decide(self, reasoning: str) -> dict:
        return {
            "reasoning": reasoning,
            "action": {"type": "kill", "target_id": ""},
        }

    def speak(self, context: dict) -> str:
        return "我是普通村民，目前还在观察局势。"
