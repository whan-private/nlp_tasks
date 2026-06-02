from werewolf.core.game_state import GameState, Phase
from werewolf.core.rule_engine import get_next_phase, check_win_condition
from werewolf.core.event_bus import EventBus, Event, EventType


class PhaseManager:
    def __init__(self, game_state: GameState, event_bus: EventBus):
        self.state = game_state
        self.bus = event_bus

    def advance_phase(self):
        self.state.phase = get_next_phase(self.state)
        if self.state.phase == Phase.DAY_DISCUSSION:
            self.state.day_num += 1
        if self.state.phase == Phase.NIGHT_WEREWOLF:
            self.state.round_num += 1
            self.state.reset_all_night()

        winner = check_win_condition(self.state)
        if winner:
            self.state.winner = winner
            self.state.phase = Phase.GAME_OVER

        self.bus.publish(Event(
            type=EventType.PHASE_CHANGE,
            data={
                "phase": self.state.phase.value,
                "round": self.state.round_num,
                "day": self.state.day_num,
                "winner": winner.value if winner else None,
            },
        ))

    @property
    def is_night(self) -> bool:
        return self.state.phase in (
            Phase.NIGHT_WEREWOLF, Phase.NIGHT_SEER, Phase.NIGHT_WITCH
        )

    @property
    def is_day(self) -> bool:
        return self.state.phase in (
            Phase.DAY_DISCUSSION, Phase.DAY_VOTE, Phase.DAY_LAST_WORDS
        )
