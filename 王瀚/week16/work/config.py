from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GameConfig:
    num_werewolves: int = 2
    num_seers: int = 1
    num_witches: int = 1
    num_villagers: int = 2
    num_hunters: int = 0
    num_guards: int = 0

    max_rounds: int = 20
    day_discussion_seconds: int = 60
    day_vote_seconds: int = 30

    @property
    def total_players(self) -> int:
        return (self.num_werewolves + self.num_seers + self.num_witches
                + self.num_villagers + self.num_hunters + self.num_guards)

    @property
    def roles(self) -> list[str]:
        roles = []
        roles.extend(["werewolf"] * self.num_werewolves)
        roles.extend(["seer"] * self.num_seers)
        roles.extend(["witch"] * self.num_witches)
        roles.extend(["villager"] * self.num_villagers)
        roles.extend(["hunter"] * self.num_hunters)
        roles.extend(["guard"] * self.num_guards)
        return roles


@dataclass
class LLMConfig:
    api_key: str = ""
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model: str = "qwen-plus"
    temperature: float = 0.8
    max_tokens: int = 512


DEFAULT_GAME_CONFIG = GameConfig()
