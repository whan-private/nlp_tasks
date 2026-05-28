from dataclasses import dataclass, field
from typing import Callable
from enum import Enum
from datetime import datetime


class EventType(Enum):
    PHASE_CHANGE = "phase_change"
    PUBLIC_SPEECH = "public_speech"
    NIGHT_ACTION = "night_action"
    VOTE_CAST = "vote_cast"
    VOTE_RESULT = "vote_result"
    PLAYER_ELIMINATED = "player_eliminated"
    PLAYER_DIED = "player_died"
    ROLE_REVEAL = "role_reveal"
    GAME_OVER = "game_over"
    SYSTEM = "system"


@dataclass
class Event:
    type: EventType
    data: dict
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    private_to: list[int] | None = None

    def is_public(self) -> bool:
        return self.private_to is None


class EventBus:
    def __init__(self):
        self._subscribers: dict[EventType, list[Callable]] = {}
        self._history: list[Event] = []

    def subscribe(self, event_type: EventType, callback: Callable):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def publish(self, event: Event):
        self._history.append(event)
        if event.type in self._subscribers:
            for cb in self._subscribers[event.type]:
                cb(event)

    def get_public_events(self, since_index: int = 0) -> list[Event]:
        return [e for e in self._history[since_index:] if e.is_public()]

    def get_events_for_player(self, player_id: int, since_index: int = 0) -> list[Event]:
        return [
            e for e in self._history[since_index:]
            if e.is_public() or (e.private_to is not None and player_id in e.private_to)
        ]

    def clear(self):
        self._subscribers.clear()
        self._history.clear()
