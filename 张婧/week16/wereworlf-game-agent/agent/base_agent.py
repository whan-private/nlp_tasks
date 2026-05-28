"""
狼人杀多智能体系统 - 基础模块
定义所有角色的抽象基类、公共接口和数据结构
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============ 枚举定义 ============

class RoleType(Enum):
    """角色类型枚举"""
    VILLAGER = "villager"  # 平民
    SEER = "seer"  # 预言家
    WITCH = "witch"  # 女巫
    HUNTER = "hunter"  # 猎人
    WEREWOLF = "werewolf"  # 狼人

    @classmethod
    def get_good_roles(cls) -> List["RoleType"]:
        """获取好人阵营角色"""
        return [cls.VILLAGER, cls.SEER, cls.WITCH, cls.HUNTER]

    @classmethod
    def get_evil_roles(cls) -> List["RoleType"]:
        """获取狼人阵营角色"""
        return [cls.WEREWOLF]

    def is_good(self) -> bool:
        """判断是否为好人阵营"""
        return self in self.get_good_roles()

    def is_evil(self) -> bool:
        """判断是否为狼人阵营"""
        return self in self.get_evil_roles()


class GamePhase(Enum):
    """游戏阶段枚举"""
    NIGHT = "night"  # 夜间
    DAY_DISCUSSION = "day_discussion"  # 白天讨论
    VOTING = "voting"  # 投票阶段
    SHOT_RESOLUTION = "shot_resolution"  # 开枪结算
    GAME_OVER = "game_over"  # 游戏结束


class ActionType(Enum):
    """行动类型枚举"""
    # 通用行动
    SPEAK = "speak"  # 发言
    VOTE = "vote"  # 投票

    # 预言家行动
    CHECK = "check"  # 查验

    # 女巫行动
    SAVE = "save"  # 救人
    POISON = "poison"  # 毒人

    # 狼人行动
    KILL = "kill"  # 刀人

    # 猎人行动
    SHOOT = "shoot"  # 开枪

    # 其他
    NONE = "none"  # 无行动


# ============ 数据类定义 ============

@dataclass
class GameConfig:
    """游戏配置"""
    total_players: int = 6
    werewolf_count: int = 2
    seer_count: int = 1
    witch_count: int = 1
    hunter_count: int = 1
    villager_count: int = 1

    # 规则配置
    witch_can_save_self: bool = False
    hunter_can_choose_not_shoot: bool = True
    allow_self_vote: bool = False
    discussion_timeout: int = 60  # 秒
    speech_limit_chars: int = 240

    # 游戏流程配置
    first_night_double_kill: bool = False  # 首夜是否允许双死
    last_words_enabled: bool = True  # 是否允许遗言

    def __post_init__(self):
        # 验证人数配置
        total = (self.werewolf_count + self.seer_count + self.witch_count +
                 self.hunter_count + self.villager_count)
        if total != self.total_players:
            raise ValueError(f"角色总数 {total} 与总人数 {self.total_players} 不匹配")


@dataclass
class PlayerInfo:
    """玩家基本信息"""
    player_id: int
    player_name: str
    role: RoleType
    is_alive: bool = True
    position: int = 0  # 座位号

    def to_dict(self) -> Dict:
        return {
            "id": self.player_id,
            "name": self.player_name,
            "role": self.role.value,
            "is_alive": self.is_alive,
            "position": self.position
        }


@dataclass
class NightInfo:
    """夜间信息（角色接收的信息）"""
    round_num: int
    # 通用信息
    attacked_player_id: Optional[int] = None  # 谁被袭击了
    attacker_ids: List[int] = field(default_factory=list)  # 袭击者

    # 预言家信息
    checked_player_id: Optional[int] = None
    check_result: Optional[str] = None

    # 女巫信息
    antidote_used: bool = False
    poison_used: bool = False
    poisoned_player_id: Optional[int] = None

    # 狼人信息
    kill_target: Optional[int] = None
    kill_success: bool = False


@dataclass
class VoteResult:
    """投票结果"""
    round_num: int
    votes: Dict[int, int]  # voter_id -> target_id
    eliminated_id: Optional[int] = None
    is_tie: bool = False
    tie_break_round: int = 0


@dataclass
class GameState:
    """游戏状态快照"""
    round_num: int
    phase: GamePhase
    alive_players: List[int]
    dead_players: List[int]
    sheriff_id: Optional[int] = None
    current_speaker: Optional[int] = None
    vote_result: Optional[VoteResult] = None
    last_death_cause: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "round": self.round_num,
            "phase": self.phase.value,
            "alive": self.alive_players.copy(),
            "dead": self.dead_players.copy(),
            "sheriff": self.sheriff_id,
            "current_speaker": self.current_speaker
        }


@dataclass
class Action:
    """行动记录"""
    player_id: int
    action_type: ActionType
    target_id: Optional[int] = None
    content: Optional[str] = None
    round_num: int = 0
    success: bool = True
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "player": self.player_id,
            "action": self.action_type.value,
            "target": self.target_id,
            "content": self.content[:100] if self.content else None,
            "round": self.round_num,
            "success": self.success,
            "time": self.timestamp.isoformat()
        }


# ============ 抽象基类 ============

class BaseAgent(ABC):
    """
    所有Agent的抽象基类

    每个Agent需要实现：
    1. 感知环境状态
    2. 根据角色做出决策
    3. 执行行动
    """

    def __init__(
            self,
            player_id: int,
            player_name: str,
            role: RoleType,
            game_config: GameConfig = None
    ):
        self.player_id = player_id
        self.player_name = player_name
        self.role = role
        self.game_config = game_config or GameConfig()

        # 状态
        self.is_alive = True
        self.round_num = 0

        # 记忆系统
        self.action_history: List[Action] = []
        self.speech_history: List[Dict] = []  # 所有发言记录
        self.vote_history: List[Dict] = []  # 投票记录

        # 游戏信息
        self.game_state: Optional[GameState] = None
        self.alive_players: List[int] = []
        self.dead_players: List[int] = []

        # 认知状态（每个Agent自己的判断）
        self.trust_scores: Dict[int, float] = {}  # 对其他玩家的信任度
        self.suspicion_scores: Dict[int, float] = {}  # 对其他玩家的怀疑度
        self.known_identities: Dict[int, str] = {}  # 已知的身份信息

        logger.info(f"Agent {self.player_name}({self.role.value}) 初始化完成")

    # ============ 抽象方法（子类必须实现） ============

    @abstractmethod
    def perceive(self, game_state: GameState, private_info: Dict) -> None:
        """
        感知环境状态

        Args:
            game_state: 游戏状态快照
            private_info: 角色私有信息（如查验结果、刀口信息等）
        """
        pass

    @abstractmethod
    def decide_speech(self, round_num: int, position: str) -> str:
        """
        决定发言内容

        Args:
            round_num: 当前轮次
            position: 发言位置 ('first', 'middle', 'last')

        Returns:
            发言文本
        """
        pass

    @abstractmethod
    def decide_vote(self, round_num: int, alive_players: List[int]) -> Optional[int]:
        """
        决定投票目标

        Args:
            round_num: 当前轮次
            alive_players: 存活玩家列表

        Returns:
            投票目标ID
        """
        pass

    @abstractmethod
    def night_action(self, round_num: int, night_info: NightInfo) -> Action:
        """
        执行夜间行动

        Args:
            round_num: 当前轮次
            night_info: 夜间信息

        Returns:
            行动记录
        """
        pass

    # ============ 公共方法 ============

    def update_state(self, game_state: GameState):
        """更新游戏状态"""
        self.game_state = game_state
        self.round_num = game_state.round_num
        self.alive_players = game_state.alive_players.copy()
        self.dead_players = game_state.dead_players.copy()

    def observe_speech(self, speaker_id: int, content: str, round_num: int):
        """
        观察发言，更新认知

        Args:
            speaker_id: 发言者ID
            content: 发言内容
            round_num: 当前轮次
        """
        # 记录发言历史
        self.speech_history.append({
            "round": round_num,
            "speaker": speaker_id,
            "content": content
        })

        # 分析发言，更新信任度和怀疑度
        self._analyze_speech(speaker_id, content)

    def observe_vote(self, voter_id: int, target_id: int, round_num: int):
        """
        观察投票，更新认知

        Args:
            voter_id: 投票者ID
            target_id: 投票目标
            round_num: 当前轮次
        """
        self.vote_history.append({
            "round": round_num,
            "voter": voter_id,
            "target": target_id
        })

        # 分析投票行为
        self._analyze_vote(voter_id, target_id)

    def observe_death(self, dead_player_id: int, cause: str, round_num: int):
        """
        观察死亡事件

        Args:
            dead_player_id: 死亡玩家ID
            cause: 死亡原因
            round_num: 当前轮次
        """
        # 更新存活/死亡列表
        if dead_player_id in self.alive_players:
            self.alive_players.remove(dead_player_id)
            self.dead_players.append(dead_player_id)

        # 更新信任度
        if dead_player_id in self.trust_scores:
            if cause in ["wolf_kill", "poison"]:
                # 被狼杀或毒死，可能是好人
                self.trust_scores[dead_player_id] = 0.8
            elif cause == "vote_out":
                # 被投票放逐，降低信任
                self.trust_scores[dead_player_id] = 0.3

    def record_action(self, action: Action):
        """记录行动"""
        self.action_history.append(action)

    def get_trusted_players(self, threshold: float = 0.7) -> List[int]:
        """获取信任度超过阈值的玩家"""
        return [pid for pid, score in self.trust_scores.items() if score >= threshold]

    def get_suspected_players(self, threshold: float = 0.6) -> List[int]:
        """获取怀疑度超过阈值的玩家"""
        return [pid for pid, score in self.suspicion_scores.items() if score >= threshold]

    def get_most_suspected(self) -> Optional[int]:
        """获取最可疑的玩家"""
        if not self.suspicion_scores:
            return None
        return max(self.suspicion_scores, key=self.suspicion_scores.get)

    def get_most_trusted(self) -> Optional[int]:
        """获取最信任的玩家"""
        if not self.trust_scores:
            return None
        return max(self.trust_scores, key=self.trust_scores.get)

    # ============ 私有方法 ============

    def _analyze_speech(self, speaker_id: int, content: str):
        """分析发言内容（子类可覆盖）"""
        # 基础分析
        suspicion_change = 0.0

        # 负向信号（增加怀疑）
        if "划水" in content or "过麦" in content:
            suspicion_change += 0.1
        if "跟票" in content or "随便" in content:
            suspicion_change += 0.05
        if len(content.strip()) < 10:
            suspicion_change += 0.08  # 发言太短

        # 正向信号（减少怀疑）
        if "逻辑" in content or "分析" in content:
            suspicion_change -= 0.05
        if "我认为" in content and len(content) > 30:
            suspicion_change -= 0.03

        # 更新怀疑度
        current = self.suspicion_scores.get(speaker_id, 0.5)
        self.suspicion_scores[speaker_id] = max(0, min(1, current + suspicion_change))

        # 更新信任度（负相关）
        trust_current = self.trust_scores.get(speaker_id, 0.5)
        self.trust_scores[speaker_id] = max(0, min(1, trust_current - suspicion_change * 0.5))

    def _analyze_vote(self, voter_id: int, target_id: int):
        """分析投票行为（子类可覆盖）"""
        # 基础分析
        pass

    # ============ 辅助方法 ============

    def is_wolf(self) -> bool:
        """判断是否为狼人"""
        return self.role == RoleType.WEREWOLF

    def is_good(self) -> bool:
        """判断是否为好人"""
        return self.role in RoleType.get_good_roles()

    def get_state_dict(self) -> Dict:
        """获取Agent状态"""
        return {
            "player_id": self.player_id,
            "player_name": self.player_name,
            "role": self.role.value,
            "is_alive": self.is_alive,
            "round": self.round_num,
            "trust_scores": self.trust_scores.copy(),
            "suspicion_scores": self.suspicion_scores.copy(),
            "known_identities": self.known_identities.copy(),
            "action_count": len(self.action_history)
        }

    def reset(self):
        """重置Agent状态（新游戏开始）"""
        self.is_alive = True
        self.round_num = 0
        self.action_history = []
        self.speech_history = []
        self.vote_history = []
        self.game_state = None
        self.alive_players = []
        self.dead_players = []
        self.trust_scores = {}
        self.suspicion_scores = {}
        self.known_identities = {}

        logger.info(f"Agent {self.player_name} 状态已重置")


class GameEngine:
    """
    游戏引擎 - 管理游戏流程
    """

    def __init__(self, config: GameConfig):
        self.config = config
        self.agents: Dict[int, BaseAgent] = {}
        self.game_state = GameState(
            round_num=0,
            phase=GamePhase.NIGHT,
            alive_players=[],
            dead_players=[]
        )
        self.round_num = 0

        # 游戏记录
        self.action_log: List[Action] = []
        self.vote_history: List[VoteResult] = []
        self.winner: Optional[str] = None

    def register_agent(self, agent: BaseAgent):
        """注册Agent"""
        self.agents[agent.player_id] = agent
        logger.info(f"注册Agent: {agent.player_name} ({agent.role.value})")

    def get_agent(self, player_id: int) -> Optional[BaseAgent]:
        """获取Agent"""
        return self.agents.get(player_id)

    def get_alive_agents(self) -> List[BaseAgent]:
        """获取存活的Agent"""
        return [a for a in self.agents.values() if a.is_alive]

    def get_alive_player_ids(self) -> List[int]:
        """获取存活玩家ID列表"""
        return [a.player_id for a in self.agents.values() if a.is_alive]

    def get_dead_player_ids(self) -> List[int]:
        """获取死亡玩家ID列表"""
        return [a.player_id for a in self.agents.values() if not a.is_alive]

    def update_game_state(self):
        """更新游戏状态"""
        self.game_state = GameState(
            round_num=self.round_num,
            phase=self.game_state.phase,
            alive_players=self.get_alive_player_ids(),
            dead_players=self.get_dead_player_ids(),
            sheriff_id=self.game_state.sheriff_id
        )

        # 通知所有存活的Agent更新状态
        for agent in self.get_alive_agents():
            agent.update_state(self.game_state)

    def log_action(self, action: Action):
        """记录行动"""
        self.action_log.append(action)

        # 通知相关Agent
        for agent in self.agents.values():
            if agent.is_alive:
                agent.record_action(action)

    def check_game_over(self) -> Tuple[bool, Optional[str]]:
        """
        检查游戏是否结束

        Returns:
            (是否结束, 获胜方)
        """
        alive_wolves = [a for a in self.get_alive_agents() if a.is_wolf()]
        alive_good = [a for a in self.get_alive_agents() if a.is_good()]

        if len(alive_wolves) == 0:
            return True, "good"
        elif len(alive_wolves) >= len(alive_good):
            return True, "werewolf"

        return False, None
