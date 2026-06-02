"""
狼人杀游戏引擎 - 状态模块
定义游戏状态、玩家状态和游戏数据类
"""

from enum import Enum
from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass, field
from datetime import datetime


class GamePhase(Enum):
    """游戏阶段枚举"""
    NIGHT = "night"  # 夜间阶段
    NIGHT_WEREWOLF = "night_werewolf"  # 狼人刀人阶段
    NIGHT_SEER = "night_seer"  # 预言家查验阶段
    NIGHT_WITCH = "night_witch"  # 女巫行动阶段
    NIGHT_HUNTER = "night_hunter"  # 猎人结算阶段（死亡开枪）
    DAY_DISCUSSION = "day_discussion"  # 白天讨论阶段
    DAY_VOTING = "day_voting"  # 白天投票阶段
    DAY_SETTLEMENT = "day_settlement"  # 白天结算阶段
    GAME_OVER = "game_over"  # 游戏结束


class PlayerStatus(Enum):
    """玩家状态"""
    ALIVE = "alive"  # 存活
    DEAD = "dead"  # 死亡
    POISONED = "poisoned"  # 被毒（当晚死亡）
    KILLED = "killed"  # 被刀（当晚死亡）


class DeathCause(Enum):
    """死亡原因"""
    WEREWOLF_KILL = "werewolf_kill"  # 狼人刀死
    VOTE_OUT = "vote_out"  # 投票放逐
    WITCH_POISON = "witch_poison"  # 女巫毒死
    HUNTER_SHOT = "hunter_shot"  # 猎人开枪
    NONE = "none"


@dataclass
class PlayerState:
    """单个玩家的状态"""
    player_id: int
    player_name: str
    role_type: str  # 角色类型
    status: PlayerStatus = PlayerStatus.ALIVE
    position: int = 0  # 座位号

    # 死亡信息
    death_round: int = 0
    death_cause: DeathCause = DeathCause.NONE

    # 技能使用状态
    has_shot: bool = False  # 猎人是否已开枪
    antidote_used: bool = False  # 女巫解药是否已用
    poison_used: bool = False  # 女巫毒药是否已用
    has_claimed: bool = False  # 是否已跳身份

    # 投票记录
    vote_target: Optional[int] = None  # 当前投票目标
    vote_history: List[int] = field(default_factory=list)  # 投票历史

    # 发言记录
    speeches: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "player_id": self.player_id,
            "player_name": self.player_name,
            "role_type": self.role_type,
            "status": self.status.value,
            "position": self.position,
            "death_round": self.death_round,
            "death_cause": self.death_cause.value if self.death_cause else None,
            "has_shot": self.has_shot,
            "antidote_used": self.antidote_used,
            "poison_used": self.poison_used,
            "vote_history": self.vote_history.copy()
        }

    def is_alive(self) -> bool:
        return self.status == PlayerStatus.ALIVE

    def kill(self, round_num: int, cause: DeathCause):
        """玩家死亡"""
        self.status = PlayerStatus.DEAD
        self.death_round = round_num
        self.death_cause = cause


@dataclass
class NightInfo:
    """夜间信息记录"""
    round_num: int

    # 狼人刀人信息
    werewolf_target: Optional[int] = None
    werewolf_attackers: List[int] = field(default_factory=list)

    # 预言家查验信息
    seer_target: Optional[int] = None
    seer_result: Optional[str] = None

    # 女巫信息
    witch_save_target: Optional[int] = None  # 被救的人
    witch_poison_target: Optional[int] = None  # 被毒的人
    antidote_used: bool = False
    poison_used: bool = False

    # 死亡信息
    death_targets: List[int] = field(default_factory=list)
    death_causes: Dict[int, DeathCause] = field(default_factory=dict)

    # 结算结果
    final_deaths: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "round": self.round_num,
            "werewolf_target": self.werewolf_target,
            "seer_target": self.seer_target,
            "seer_result": self.seer_result,
            "witch_save_target": self.witch_save_target,
            "witch_poison_target": self.witch_poison_target,
            "final_deaths": self.final_deaths.copy()
        }


@dataclass
class VoteInfo:
    """投票信息"""
    round_num: int
    votes: Dict[int, int] = field(default_factory=dict)  # voter -> target
    eliminated_player: Optional[int] = None
    is_tie: bool = False
    tie_break_round: int = 0

    def add_vote(self, voter_id: int, target_id: int):
        self.votes[voter_id] = target_id

    def get_vote_count(self) -> Dict[int, int]:
        """统计每个目标的得票数"""
        counts = {}
        for target in self.votes.values():
            counts[target] = counts.get(target, 0) + 1
        return counts

    def get_eliminated(self) -> Optional[int]:
        """获取被放逐的玩家"""
        counts = self.get_vote_count()
        if not counts:
            return None

        max_count = max(counts.values())
        candidates = [p for p, c in counts.items() if c == max_count]

        if len(candidates) == 1:
            self.eliminated_player = candidates[0]
            self.is_tie = False
            return candidates[0]
        else:
            self.is_tie = True
            return None


@dataclass
class GameState:
    """游戏全局状态"""
    game_id: str
    round_num: int = 0
    phase: GamePhase = GamePhase.NIGHT

    # 玩家信息
    players: Dict[int, PlayerState] = field(default_factory=dict)
    player_order: List[int] = field(default_factory=list)  # 座位顺序

    # 游戏配置
    total_players: int = 0
    alive_count: int = 0
    werewolf_count: int = 0
    good_count: int = 0

    # 特殊玩家
    sheriff_id: Optional[int] = None  # 警长ID
    current_speaker: Optional[int] = None  # 当前发言玩家
    speech_index: int = 0  # 发言索引

    # 本轮信息
    night_info: Optional[NightInfo] = None
    vote_info: Optional[VoteInfo] = None

    # 历史记录
    night_history: List[NightInfo] = field(default_factory=list)
    vote_history: List[VoteInfo] = field(default_factory=list)

    # 游戏结束标志
    is_game_over: bool = False
    winner: Optional[str] = None  # 'good' or 'werewolf'

    def get_alive_players(self) -> List[int]:
        """获取存活玩家ID列表"""
        return [pid for pid, p in self.players.items() if p.is_alive()]

    def get_dead_players(self) -> List[int]:
        """获取死亡玩家ID列表"""
        return [pid for pid, p in self.players.items() if not p.is_alive()]

    def get_alive_werewolves(self) -> List[int]:
        """获取存活的狼人ID列表"""
        return [pid for pid, p in self.players.items()
                if p.is_alive() and p.role_type == "werewolf"]

    def get_alive_good_players(self) -> List[int]:
        """获取存活的好人ID列表"""
        good_roles = ["villager", "seer", "witch", "hunter"]
        return [pid for pid, p in self.players.items()
                if p.is_alive() and p.role_type in good_roles]

    def get_player_by_id(self, player_id: int) -> Optional[PlayerState]:
        return self.players.get(player_id)

    def get_player_by_name(self, name: str) -> Optional[PlayerState]:
        for player in self.players.values():
            if player.player_name == name:
                return player
        return None

    def update_counts(self):
        """更新计数"""
        self.alive_count = len(self.get_alive_players())
        self.werewolf_count = len(self.get_alive_werewolves())
        self.good_count = self.alive_count - self.werewolf_count

    def check_game_over(self) -> Tuple[bool, Optional[str]]:
        """
        检查游戏是否结束

        Returns:
            (是否结束, 获胜方)
        """
        self.update_counts()

        if self.werewolf_count == 0:
            self.is_game_over = True
            self.winner = "good"
            self.phase = GamePhase.GAME_OVER
            return True, "good"

        if self.werewolf_count >= self.good_count:
            self.is_game_over = True
            self.winner = "werewolf"
            self.phase = GamePhase.GAME_OVER
            return True, "werewolf"

        return False, None

    def next_round(self):
        """进入下一轮"""
        self.round_num += 1
        self.phase = GamePhase.NIGHT
        self.night_info = NightInfo(round_num=self.round_num)
        self.vote_info = None
        self.current_speaker = None
        self.speech_index = 0

        # 重置玩家投票状态
        for player in self.players.values():
            if player.is_alive():
                player.vote_target = None

    def to_dict(self) -> Dict:
        return {
            "game_id": self.game_id,
            "round": self.round_num,
            "phase": self.phase.value,
            "alive_count": self.alive_count,
            "werewolf_count": self.werewolf_count,
            "sheriff": self.sheriff_id,
            "is_game_over": self.is_game_over,
            "winner": self.winner,
            "players": {pid: p.to_dict() for pid, p in self.players.items()}
        }