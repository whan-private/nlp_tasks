from werewolf.agents.base import BaseAgent
from werewolf.core.game_state import GameState
from werewolf.llm.prompts import DECISION_PROMPTS


class SeerAgent(BaseAgent):
    def night_action(self, state: GameState) -> dict:
        alive_others = [p.name for p in state.alive_players if p.id != self.player_id]
        prompt = DECISION_PROMPTS["seer_night"]
        result = self._llm_json(prompt, state)
        target = result.get("target", "")
        if target and target in alive_others:
            return {"target": target, "reason": result.get("reason", "")}
        return {"target": alive_others[0] if alive_others else "", "reason": "random"}
