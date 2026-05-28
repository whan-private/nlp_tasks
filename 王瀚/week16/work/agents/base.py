from werewolf.core.game_state import GameState, Phase, Team
from werewolf.core.event_bus import EventBus, Event, EventType
from werewolf.llm.client import LLMClient
from werewolf.llm.prompts import (
    system_prompt, format_game_context, DECISION_PROMPTS,
)
from werewolf.memory.public import PublicMemory
from werewolf.memory.private import PrivateMemory


class BaseAgent:
    def __init__(self, player_id: int, name: str, role: str,
                 llm_client: LLMClient, teammates: list[str] | None = None):
        self.player_id = player_id
        self.name = name
        self.role = role
        self.team = Team.WEREWOLF if role == "werewolf" else Team.VILLAGE
        self.llm = llm_client
        self.system = system_prompt(role, name, teammates)
        self.public_memory = PublicMemory()
        self.private_memory = PrivateMemory(player_id, role)

    def on_event(self, event: Event):
        self.public_memory.add_event(event)
        if not event.is_public() and event.private_to and self.player_id in event.private_to:
            self.private_memory.add_night_result(event.data)

    def _build_context(self, state: GameState) -> str:
        return format_game_context(
            player_name=self.name,
            day=state.day_num,
            phase=state.phase.value,
            alive_players=[p.name for p in state.alive_players],
            chat_history=self.public_memory.get_chat_history(),
            vote_history=self.public_memory.get_vote_summary(),
            death_history=self.public_memory.get_death_history(),
            private_info=self.private_memory.get_night_summary(),
        )

    def _llm_chat(self, user_prompt: str, state: GameState | None = None) -> str:
        ctx = self._build_context(state or self._cached_state)
        messages = [
            {"role": "system", "content": self.system},
            {"role": "user", "content": f"{ctx}\n\n{user_prompt}"},
        ]
        return self.llm.chat(messages, temperature=0.8, max_tokens=256)

    def _llm_json(self, user_prompt: str, state: GameState | None = None) -> dict:
        ctx = self._build_context(state or self._cached_state)
        messages = [
            {"role": "system", "content": self.system},
            {"role": "user", "content": f"{ctx}\n\n{user_prompt}"},
        ]
        return self.llm.chat_json(messages, temperature=0.5, max_tokens=256)

    # ---- Public actions ----

    def make_speech(self, state: GameState) -> str:
        text = self._llm_chat(DECISION_PROMPTS["speech"], state)
        return text[:200]

    def vote(self, state: GameState) -> tuple[str, str]:
        result = self._llm_json(DECISION_PROMPTS["vote"], state)
        target = result.get("target", "")
        reason = result.get("reason", "")
        return target, reason

    def last_words(self, state: GameState) -> str:
        text = self._llm_chat(DECISION_PROMPTS["last_words"], state)
        return text[:160]

    # ---- Night actions ----

    def night_action(self, state: GameState) -> dict:
        self._cached_state = state
        raise NotImplementedError

    # ---- Mock fallback for testing ----

    def mock_speech(self) -> str:
        return "...(thinking)..."

    def mock_vote(self, candidates: list[str]) -> str:
        return candidates[0] if candidates else ""

    def mock_night_action(self, targets: list[str]) -> str:
        return targets[0] if targets else ""
