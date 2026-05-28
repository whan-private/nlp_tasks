from werewolf.agents.base import BaseAgent
from werewolf.core.game_state import GameState
from werewolf.llm.prompts import DECISION_PROMPTS


class WitchAgent(BaseAgent):
    def night_action(self, state: GameState) -> dict:
        witch = state.get_player(self.player_id)
        killed_player = None
        nr = self.private_memory.night_results
        for r in reversed(nr):
            data = r.get("data", r)
            if "target_id" in data:
                killed_id = data["target_id"]
                killed = state.get_player(killed_id)
                killed_player = killed.name if killed else "unknown"
                break

        prompt = DECISION_PROMPTS["witch_night"].format(
            killed_player=killed_player or "无",
            has_antidote=str(witch.witch_has_antidote if witch else False),
            has_poison=str(witch.witch_has_poison if witch else False),
        )
        result = self._llm_json(prompt, state)
        return {
            "save": result.get("save", False),
            "poison_target": result.get("poison_target", None),
            "reason": result.get("reason", ""),
        }
