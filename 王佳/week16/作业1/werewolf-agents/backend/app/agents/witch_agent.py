from app.agents.base_agent import BaseAgent, GameState, VisibleInfo
from app.services.role_system import Witch


class WitchAgent(BaseAgent):
    """女巫 Agent — 拥有解药和毒药各一瓶，合理使用帮助村民阵营。"""

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
                "action": "save_or_poison",
                "antidote_available": self.role.can_save(),
                "poison_available": self.role.can_poison(),
            },
        )
        return info

    def reason(self, visible_info: VisibleInfo) -> str:
        lines = [
            f"玩家 {self.player_id}（女巫）正在推理",
            f"当前回合: 第 {visible_info.round} 轮",
            f"当前阶段: {visible_info.phase}",
            f"解药可用: {visible_info.extra.get('antidote_available')}",
            f"毒药可用: {visible_info.extra.get('poison_available')}",
        ]
        if visible_info.phase == "night":
            if visible_info.extra.get("night_kill_target"):
                lines.append(f"今夜狼人击杀目标: {visible_info.extra['night_kill_target']}")
            if visible_info.extra.get("antidote_available"):
                lines.append("策略：第一晚通常使用解药救人以保留信息最大化")
            if visible_info.extra.get("poison_available"):
                lines.append("策略：若确认某玩家为狼人，可考虑使用毒药")
        else:
            lines.append("白天策略：隐藏女巫身份，以村民身份发言和投票")
        return "\n".join(lines)

    def decide(self, reasoning: str) -> dict:
        return {
            "reasoning": reasoning,
            "action": {"type": "skip", "target_id": None},
        }

    def speak(self, context: dict) -> str:
        return "我认为应该更加谨慎地分析每个人的发言。"
