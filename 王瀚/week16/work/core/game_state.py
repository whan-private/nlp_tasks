from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Phase(Enum):
    NIGHT_WEREWOLF = "night_werewolf"
    NIGHT_SEER = "night_seer"
    NIGHT_WITCH = "night_witch"
    DAY_DISCUSSION = "day_discussion"
    DAY_VOTE = "day_vote"
    DAY_LAST_WORDS = "day_last_words"
    GAME_OVER = "game_over"


class Team(Enum):
    WEREWOLF = "werewolf"
    VILLAGE = "village"


@dataclass
class Player:
    id: int
    name: str
    role: str
    team: Team
    alive: bool = True
    is_sheriff: bool = False
    protected: bool = False
    poisoned_tonight: bool = False
    killed_tonight: bool = False
    voted_out: bool = False
    witch_saved: bool = False
    witch_has_antidote: bool = True
    witch_has_poison: bool = True

    def reset_night(self):
        self.protected = False
        self.poisoned_tonight = False
        self.killed_tonight = False
        self.witch_saved = False


@dataclass
class GameState:
    players: list[Player] = field(default_factory=list)
    phase: Phase = Phase.NIGHT_WEREWOLF
    round_num: int = 0
    day_num: int = 0
    winner: Optional[Team] = None
    eliminated_history: list[dict] = field(default_factory=list)

    @property
    def alive_players(self) -> list[Player]:
        return [p for p in self.players if p.alive]

    @property
    def dead_players(self) -> list[Player]:
        return [p for p in self.players if not p.alive]

    def get_player(self, player_id: int) -> Optional[Player]:
        for p in self.players:
            if p.id == player_id:
                return p
        return None

    def get_player_by_name(self, name: str) -> Optional[Player]:
        for p in self.players:
            if p.name == name:
                return p
        return None

    def get_alive_wolves(self) -> list[Player]:
        return [p for p in self.players if p.alive and p.team == Team.WEREWOLF]

    def count_team(self) -> dict:
        alive_players = self.alive_players
        wolf_count = sum(1 for p in alive_players if p.team == Team.WEREWOLF)
        village_count = len(alive_players) - wolf_count
        return {"wolf": wolf_count, "village": village_count}

    def eliminate(self, player_id: int, reason: str):
        player = self.get_player(player_id)
        if player and player.alive:
            player.alive = False
            self.eliminated_history.append({
                "round": self.round_num,
                "day": self.day_num,
                "player_id": player_id,
                "player_name": player.name,
                "role": player.role,
                "reason": reason,
            })

    def reset_all_night(self):
        for p in self.players:
            p.reset_night()
