from werewolf.core.game_state import GameState, Team
from werewolf.llm.client import LLMClient
from werewolf.agents.base import BaseAgent
from werewolf.agents.werewolf import WerewolfAgent
from werewolf.agents.seer import SeerAgent
from werewolf.agents.witch import WitchAgent
from werewolf.agents.villager import VillagerAgent


def create_agents(state: GameState, llm_client: LLMClient) -> dict[int, BaseAgent]:
    wolf_names = [p.name for p in state.players if p.team == Team.WEREWOLF]
    agents = {}

    for player in state.players:
        teammates = None
        if player.team == Team.WEREWOLF:
            teammates = [n for n in wolf_names if n != player.name]

        if player.role == "werewolf":
            agent = WerewolfAgent(player.id, player.name, player.role, llm_client, teammates)
        elif player.role == "seer":
            agent = SeerAgent(player.id, player.name, player.role, llm_client)
        elif player.role == "witch":
            agent = WitchAgent(player.id, player.name, player.role, llm_client)
        else:
            agent = VillagerAgent(player.id, player.name, player.role, llm_client)

        agents[player.id] = agent

    return agents
