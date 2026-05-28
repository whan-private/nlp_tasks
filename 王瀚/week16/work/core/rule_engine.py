import random
from werewolf.core.game_state import GameState, Player, Team, Phase
from werewolf.config import GameConfig


def assign_roles(config: GameConfig, player_names: list[str]) -> GameState:
    if len(player_names) != config.total_players:
        raise ValueError(f"Need {config.total_players} players, got {len(player_names)}")

    roles = config.roles[:]
    random.shuffle(roles)

    state = GameState()
    for i, name in enumerate(player_names):
        role = roles[i]
        team = Team.WEREWOLF if role == "werewolf" else Team.VILLAGE
        state.players.append(Player(
            id=i,
            name=name,
            role=role,
            team=team,
        ))
    return state


def check_win_condition(state: GameState) -> Team | None:
    counts = state.count_team()
    if counts["wolf"] == 0:
        return Team.VILLAGE
    if counts["wolf"] >= counts["village"]:
        return Team.WEREWOLF
    return None


def count_players(state: GameState) -> dict:
    alive = state.alive_players
    return {
        "total": len(alive),
        "wolf": sum(1 for p in alive if p.team == Team.WEREWOLF),
        "village": sum(1 for p in alive if p.team == Team.VILLAGE),
    }


def get_next_phase(state: GameState) -> Phase:
    if state.winner is not None:
        return Phase.GAME_OVER
    if state.phase == Phase.NIGHT_WEREWOLF:
        return Phase.NIGHT_SEER
    if state.phase == Phase.NIGHT_SEER:
        return Phase.NIGHT_WITCH
    if state.phase == Phase.NIGHT_WITCH:
        return Phase.DAY_DISCUSSION
    if state.phase == Phase.DAY_DISCUSSION:
        return Phase.DAY_VOTE
    if state.phase == Phase.DAY_VOTE:
        return Phase.DAY_LAST_WORDS
    if state.phase == Phase.DAY_LAST_WORDS:
        return Phase.NIGHT_WEREWOLF
    return Phase.GAME_OVER
