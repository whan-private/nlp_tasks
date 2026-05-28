from werewolf.agents.base import BaseAgent
from werewolf.core.game_state import GameState


class VillagerAgent(BaseAgent):
    def night_action(self, state: GameState) -> dict:
        return {}
