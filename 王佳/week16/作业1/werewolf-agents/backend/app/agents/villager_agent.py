from app.agents.base_agent import BaseAgent, GameState, VisibleInfo
from app.services.role_system import Villager


class VillagerAgent(BaseAgent):
    """村民 Agent — 通过推理和投票找出狼人。"""

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
                "action": "vote",
            },
        )
        return info

    def reason(self, visible_info: VisibleInfo) -> str:
        lines = [
            f"玩家 {self.player_id}（村民）正在推理",
            f"当前回合: 第 {visible_info.round} 轮",
            f"当前阶段: {visible_info.phase}",
            f"存活玩家: {[p for p in visible_info.alive_players]}",
            f"已死亡玩家: {visible_info.dead_players}",
        ]
        if visible_info.phase == "day":
            lines.append("推理策略：")
            lines.append("- 分析每个玩家的发言，寻找矛盾点")
            lines.append("- 追踪投票模式，狼人倾向于保护队友")
            lines.append("- 如果有预言家跳身份，综合其查验信息判断")
            if visible_info.alive_players:
                lines.append(f"- 重点观察: {[p for p in visible_info.alive_players[:3]]}")
        return "\n".join(lines)

    def decide(self, reasoning: str) -> dict:
        return {
            "reasoning": reasoning,
            "action": {"type": "vote", "target_id": ""},
        }

    def speak(self, context: dict) -> str:
        return "我是普通村民，目前观察到一些玩家的行为存在不一致，需要更多的信息和发言来判断。"
