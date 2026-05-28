from werewolf.agents.base import BaseAgent
from werewolf.core.game_state import GameState, Team
from werewolf.llm.prompts import DECISION_PROMPTS


class WerewolfAgent(BaseAgent):
    def night_action(self, state: GameState) -> dict:
        alive_villagers = [p.name for p in state.alive_players if p.team == Team.VILLAGE]
        prompt = DECISION_PROMPTS["werewolf_night"]
        result = self._llm_json(prompt, state)
        target = result.get("target", "")
        if target and target in alive_villagers:
            return {"target": target, "reason": result.get("reason", "")}
        return {"target": alive_villagers[0] if alive_villagers else "", "reason": "random"}

    def mock_night_action(self, targets: list[str]) -> str:
        return targets[0] if targets else ""
