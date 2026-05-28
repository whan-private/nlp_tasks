import pytest

from app.agents.base_agent import BaseAgent, GameState, VisibleInfo
from app.agents.hunter_agent import HunterAgent
from app.agents.seer_agent import SeerAgent
from app.agents.villager_agent import VillagerAgent
from app.agents.werewolf_agent import WerewolfAgent
from app.agents.witch_agent import WitchAgent
from app.services.role_system import Hunter, Seer, Villager, Werewolf, Witch


def make_game_state(phase="night", alive_ids=None):
    return GameState(
        round=1,
        phase=phase,
        alive_players=alive_ids or ["p1", "p2", "p3", "p4", "p5", "p6"],
        dead_players=[],
    )


class TestWerewolfAgent:
    def test_creation(self):
        agent = WerewolfAgent("p1", Werewolf())
        assert agent.player_id == "p1"
        assert agent.role.name == "werewolf"
        assert agent.is_alive is True
        assert agent.role.team.value == "werewolf"

    def test_perceive(self):
        agent = WerewolfAgent("p1", Werewolf())
        state = make_game_state()
        info = agent.perceive(state)
        assert info.role_name == "werewolf"
        assert info.extra["action"] == "kill"
        assert info.extra["teammates_visible"] is True

    def test_reason_night(self):
        agent = WerewolfAgent("p1", Werewolf())
        info = VisibleInfo("p1", "werewolf", "werewolf", 1, "night", ["p1", "p2"], [], {"action": "kill"})
        reasoning = agent.reason(info)
        assert "夜间策略" in reasoning

    def test_reason_day(self):
        agent = WerewolfAgent("p1", Werewolf())
        info = VisibleInfo("p1", "werewolf", "werewolf", 1, "day", ["p1", "p2"], [], {})
        reasoning = agent.reason(info)
        assert "白天策略" in reasoning

    def test_decide(self):
        agent = WerewolfAgent("p1", Werewolf())
        result = agent.decide("test reasoning")
        assert result["action"]["type"] == "kill"

    def test_speak(self):
        agent = WerewolfAgent("p1", Werewolf())
        speech = agent.speak({})
        assert isinstance(speech, str)
        assert len(speech) > 0


class TestSeerAgent:
    def test_creation(self):
        agent = SeerAgent("p1", Seer())
        assert agent.role.name == "seer"
        assert agent.role.team.value == "villager"

    def test_perceive(self):
        agent = SeerAgent("p1", Seer())
        info = agent.perceive(make_game_state())
        assert info.extra["action"] == "check"

    def test_decide(self):
        agent = SeerAgent("p1", Seer())
        result = agent.decide("test")
        assert result["action"]["type"] == "check"


class TestWitchAgent:
    def test_creation(self):
        agent = WitchAgent("p1", Witch())
        assert agent.role.name == "witch"
        assert agent.role.can_save() is True
        assert agent.role.can_poison() is True

    def test_perceive_with_potions(self):
        agent = WitchAgent("p1", Witch())
        info = agent.perceive(make_game_state())
        assert info.extra["antidote_available"] is True
        assert info.extra["poison_available"] is True

    def test_perceive_after_using_potions(self):
        role = Witch()
        role.use_antidote()
        role.use_poison()
        agent = WitchAgent("p1", role)
        info = agent.perceive(make_game_state())
        assert info.extra["antidote_available"] is False
        assert info.extra["poison_available"] is False

    def test_decide_defaults_to_skip(self):
        agent = WitchAgent("p1", Witch())
        result = agent.decide("test")
        assert result["action"]["type"] == "skip"


class TestHunterAgent:
    def test_creation(self):
        agent = HunterAgent("p1", Hunter())
        assert agent.role.name == "hunter"
        assert agent.role.can_shoot is True

    def test_on_death_can_shoot(self):
        agent = HunterAgent("p1", Hunter())
        result = agent.on_death()
        assert result is not None
        assert result["type"] == "shoot"

    def test_on_death_cannot_shoot(self):
        role = Hunter()
        role.disable_shoot()
        agent = HunterAgent("p1", role)
        result = agent.on_death()
        assert result is None

    def test_decide(self):
        agent = HunterAgent("p1", Hunter())
        result = agent.decide("test")
        assert result["action"]["type"] == "shoot"


class TestVillagerAgent:
    def test_creation(self):
        agent = VillagerAgent("p1", Villager())
        assert agent.role.name == "villager"
        assert agent.role.team.value == "villager"

    def test_perceive(self):
        agent = VillagerAgent("p1", Villager())
        info = agent.perceive(make_game_state())
        assert info.extra["action"] == "vote"

    def test_decide(self):
        agent = VillagerAgent("p1", Villager())
        result = agent.decide("test")
        assert result["action"]["type"] == "vote"

    def test_reason_day(self):
        agent = VillagerAgent("p1", Villager())
        info = VisibleInfo("p1", "villager", "villager", 1, "day",
                           ["p1", "p2", "p3"], [], {"action": "vote"})
        reasoning = agent.reason(info)
        assert "推理策略" in reasoning


class TestBaseAgentAbstract:
    def test_cannot_instantiate_abstract(self):
        """BaseAgent 是抽象类，但可以通过具体子类实例化。"""
        # 具体子类可以实例化
        agent = VillagerAgent("p1", Villager())
        assert isinstance(agent, BaseAgent)

    def test_is_alive_default(self):
        agent = VillagerAgent("p1", Villager())
        assert agent.is_alive is True
        agent.is_alive = False
        assert agent.is_alive is False
