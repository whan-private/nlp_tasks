"""
狼人杀游戏 - 狼人角色模块
狼人是邪恶阵营的核心成员，拥有夜间刀人和团队协作的能力
"""

from enum import Enum
from typing import Optional, List, Dict, Any, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging
import random

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class WerewolfRole(Enum):
    """狼人特殊身份类型"""
    COMMON = "common"  # 普通狼人
    WOLF_KING = "wolf_king"  # 狼王（死后可开枪）
    WHITE_WOLF_KING = "white_wolf_king"  # 白狼王（自爆可带走一人）


class NightAction(Enum):
    """狼人夜间行动"""
    KILL = "kill"  # 刀人
    SELF_KILL = "self_kill"  # 自刀
    NONE = "none"  # 空刀


class WerewolfStrategy(Enum):
    """狼人伪装策略"""
    DEEP_WATER = "deep_water"  # 深水狼：低调隐藏
    HARD_JUMP = "hard_jump"  # 悍跳狼：冒充预言家
    WITCH_HUNT = "witch_hunt"  # 倒钩狼：站边真预言家
    SILENT = "silent"  # 沉默狼：尽量少发言
    AGGRESSIVE = "aggressive"  # 激进狼：主动攻击


@dataclass
class KillRecord:
    """刀人记录"""
    round_num: int
    target_id: int
    target_name: str
    success: bool
    is_self_kill: bool = False
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "round": self.round_num,
            "target": self.target_id,
            "success": self.success,
            "is_self_kill": self.is_self_kill,
            "time": self.timestamp.isoformat()
        }


@dataclass
class WerewolfMemory:
    """狼人的记忆单元"""
    round_num: int
    event_type: str  # 'kill', 'speech', 'vote', 'death', 'strategy_change'
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


class Werewolf:
    """
    狼人角色类

    狼人是邪恶阵营的核心成员，拥有团队协作和夜间袭击的能力。
    狼人的核心价值在于：
    1. 夜间刀人，减少好人阵营人数
    2. 白天伪装身份，混淆视听
    3. 团队配合，制造逻辑漏洞
    4. 悍跳预言家，抢夺话语权

    属性说明：
    - player_id: 玩家ID
    - player_name: 玩家名称
    - is_alive: 是否存活
    - team_id: 队伍ID（狼人队伍）
    - teammates: 狼队友ID列表
    - can_kill: 是否可以刀人（每轮一次）
    - kill_history: 刀人历史记录
    - pretend_role: 伪装的身份
    - strategy: 当前使用的策略
    - target_fake_identity: 伪造的查验结果
    - is_seer_claimer: 是否假跳预言家
    - self_kill_planned: 是否计划自刀
    """

    def __init__(
            self,
            player_id: int,
            player_name: str,
            team_id: int = 1,
            wolf_type: WerewolfRole = WerewolfRole.COMMON
    ):
        """
        初始化狼人角色

        Args:
            player_id: 玩家ID
            player_name: 玩家名称
            team_id: 队伍ID（狼人队伍标识）
            wolf_type: 狼人特殊身份类型
        """
        self.player_id = player_id
        self.player_name = player_name
        self.role_type = "werewolf"
        self.wolf_type = wolf_type
        self.is_alive = True

        # 团队信息
        self.team_id = team_id
        self.teammates: Set[int] = set()  # 狼队友ID集合（不包含自己）
        self.all_wolves: Set[int] = set()  # 所有狼人ID（包含自己）

        # 刀人相关
        self.can_kill = True  # 每轮可以刀人一次
        self.kill_history: List[KillRecord] = []
        self.current_kill_target: Optional[int] = None

        # 伪装相关
        self.pretend_role = "villager"  # 伪装的身份
        self.strategy = WerewolfStrategy.DEEP_WATER
        self.fake_checks: Dict[int, str] = {}  # 伪造的查验结果 {target: "good"/"wolf"}
        self.is_seer_claimer = False  # 是否假跳预言家
        self.seer_claim_round: Optional[int] = None

        # 自刀相关
        self.self_kill_planned = False
        self.self_kill_round: Optional[int] = None

        # 信息收集
        self.known_seer: Optional[int] = None  # 认为的真预言家
        self.known_witch: Optional[int] = None  # 推测的女巫
        self.known_hunter: Optional[int] = None  # 推测的猎人
        self.kill_priority: List[str] = ["seer", "witch", "hunter", "villager"]  # 刀人优先级

        # 投票协调
        self.vote_coordination: Dict[int, int] = {}  # 约定投票目标 {round: target}

        # 记忆系统
        self.memory: List[WerewolfMemory] = []
        self.speech_history: List[Dict] = []

        # 状态记录
        self.exposed_as_wolf: bool = False  # 是否被查出
        self.survival_rounds: int = 0  # 存活轮数

        logger.info(f"狼人 {player_name}(ID:{player_id}) 初始化完成 - 类型:{wolf_type.value}")

    # ============ 团队协作方法 ============

    def set_teammates(self, teammates: List[int]):
        """设置狼队友"""
        self.teammates = set(teammates)
        self.all_wolves = self.teammates | {self.player_id}
        logger.info(f"狼人 {self.player_name} 的队友: {self.teammates}")

    def teammate_chat(self, message: str, round_num: int):
        """
        狼队夜间密谋（只有狼人能看到）

        Args:
            message: 消息内容
            round_num: 当前轮次
        """
        self.memory.append(WerewolfMemory(
            round_num=round_num,
            event_type="team_chat",
            content=f"团队信息: {message}"
        ))
        logger.info(f"狼队密谋 (Round {round_num}): {self.player_name} 发送: {message[:50]}")

    def coordinate_vote(self, round_num: int, target_id: int):
        """协调投票目标（狼队统一冲票）"""
        self.vote_coordination[round_num] = target_id
        logger.info(f"狼人 {self.player_name} 在{round_num}轮约定投票给 {target_id}")

    def get_agreed_vote_target(self, round_num: int) -> Optional[int]:
        """获取约定的投票目标"""
        return self.vote_coordination.get(round_num)

    # ============ 夜间刀人方法 ============

    def can_perform_kill(self) -> bool:
        """检查是否可以进行刀人"""
        return self.is_alive and self.can_kill

    def decide_kill_target(
            self,
            alive_players: List[int],
            player_roles: Dict[int, Optional[str]],  # 推测的角色
            round_num: int
    ) -> Tuple[Optional[int], bool]:
        """
        决定刀人目标

        刀人策略：
        1. 优先刀预言家（信息位）
        2. 其次刀女巫（威胁最大）
        3. 再刀猎人（有反杀能力）
        4. 最后刀平民

        Args:
            alive_players: 存活玩家列表
            player_roles: 推测的玩家角色
            round_num: 当前轮次

        Returns:
            (目标ID, 是否自刀)
        """
        if not self.can_perform_kill():
            return None, False

        # 过滤掉队友和自己
        candidates = [p for p in alive_players if p not in self.all_wolves]

        if not candidates:
            return None, False

        # 检查是否计划自刀
        if self.self_kill_planned and round_num == self.self_kill_round:
            return self.player_id, True

        # 按优先级选择目标
        for role_type in self.kill_priority:
            for candidate in candidates:
                guessed_role = player_roles.get(candidate, "")
                if role_type in guessed_role.lower():
                    return candidate, False

        # 默认：随机选择一个非队友
        import random
        return random.choice(candidates), False

    def perform_kill(self, target_id: int, round_num: int, success: bool = True) -> KillRecord:
        """
        执行刀人

        Args:
            target_id: 目标玩家ID
            round_num: 当前轮次
            success: 是否成功（女巫解救会失败）

        Returns:
            刀人记录
        """
        if not self.can_perform_kill():
            raise ValueError(f"狼人 {self.player_name} 无法进行刀人")

        is_self_kill = (target_id == self.player_id)

        record = KillRecord(
            round_num=round_num,
            target_id=target_id,
            target_name=f"Player_{target_id}",
            success=success,
            is_self_kill=is_self_kill
        )
        self.kill_history.append(record)
        self.current_kill_target = target_id
        self.can_kill = False

        # 记录记忆
        action_type = "自刀" if is_self_kill else "刀人"
        result = "成功" if success else "失败（被救）"
        self.memory.append(WerewolfMemory(
            round_num=round_num,
            event_type="kill",
            content=f"{action_type} {target_id}号，{result}"
        ))

        logger.info(f"狼人 {self.player_name} 在{round_num}轮{'自刀' if is_self_kill else f'刀{target_id}号'}，{result}")

        return record

    def plan_self_kill(self, round_num: int):
        """
        计划自刀（骗取女巫解药）

        Args:
            round_num: 计划自刀的轮次
        """
        self.self_kill_planned = True
        self.self_kill_round = round_num
        logger.info(f"狼人 {self.player_name} 计划在{round_num}轮自刀")

    def cancel_self_kill(self):
        """取消自刀计划"""
        self.self_kill_planned = False
        self.self_kill_round = None
        logger.info(f"狼人 {self.player_name} 取消自刀计划")

    def reset_night_action(self):
        """重置夜间行动（进入新的一天时调用）"""
        self.can_kill = True
        self.current_kill_target = None

    # ============ 伪装策略方法 ============

    def set_strategy(self, strategy: WerewolfStrategy):
        """设置伪装策略"""
        self.strategy = strategy

        # 根据策略调整伪装身份
        if strategy == WerewolfStrategy.HARD_JUMP:
            self.pretend_role = "seer"
            self.is_seer_claimer = True
        elif strategy == WerewolfStrategy.DEEP_WATER:
            self.pretend_role = "villager"
            self.is_seer_claimer = False
        elif strategy == WerewolfStrategy.WITCH_HUNT:
            self.pretend_role = "villager"
            self.is_seer_claimer = False
        elif strategy == WerewolfStrategy.SILENT:
            self.pretend_role = "villager"
            self.is_seer_claimer = False
        elif strategy == WerewolfStrategy.AGGRESSIVE:
            self.pretend_role = "villager"
            self.is_seer_claimer = False

        self.memory.append(WerewolfMemory(
            round_num=0,
            event_type="strategy_change",
            content=f"切换策略为 {strategy.value}，伪装成 {self.pretend_role}"
        ))

        logger.info(f"狼人 {self.player_name} 切换策略为 {strategy.value}")

    def set_fake_check(self, target_id: int, result: str):
        """
        设置伪造的查验结果（悍跳时使用）

        Args:
            target_id: 目标玩家ID
            result: 结果 ('good' 金水, 'wolf' 查杀)
        """
        self.fake_checks[target_id] = result
        logger.info(f"狼人 {self.player_name} 伪造查验: {target_id}号是{result}")

    def generate_hard_jump_speech(self, round_num: int) -> str:
        """
        生成悍跳发言（冒充预言家）

        Returns:
            悍跳发言文本
        """
        if not self.fake_checks:
            # 随机生成一个假查验
            import random
            fake_target = random.randint(1, 12)
            fake_result = random.choice(["金水", "查杀"])
            self.set_fake_check(fake_target, "good" if fake_result == "金水" else "wolf")

        # 获取最近的假查验
        last_target = list(self.fake_checks.keys())[-1]
        last_result = self.fake_checks[last_target]
        result_text = "金水" if last_result == "good" else "查杀"

        speech_parts = [
            "我是预言家，",
            f"昨晚查验了{last_target}号玩家，",
            f"是{result_text}。",
            "警徽流先留一个...",
            "请好人玩家们投给我警徽，我会带领大家找出所有狼人。过。"
        ]

        return "".join(speech_parts)

    def generate_deep_water_speech(self, round_num: int) -> str:
        """
        生成深水狼发言（伪装成平民）

        Returns:
            深水狼发言文本
        """
        speeches = [
            "我是好人，过。",
            "平民一个，听预言家的。",
            "我是村民，没什么信息，这一轮我会认真听大家发言。",
            "好人，跟警长投票。"
        ]
        return random.choice(speeches)

    def generate_witch_hunt_speech(self, round_num: int, real_seer_id: int) -> str:
        """
        生成倒钩狼发言（站边真预言家）

        Args:
            round_num: 当前轮次
            real_seer_id: 真预言家ID

        Returns:
            倒钩狼发言文本
        """
        return f"我相信{real_seer_id}号是预言家，他的发言逻辑清晰，我会跟着{real_seer_id}号投票。过。"

    def generate_speech(
            self,
            round_num: int,
            position: str,
            real_seer_id: Optional[int] = None
    ) -> str:
        """
        根据当前策略生成发言

        Args:
            round_num: 当前轮次
            position: 发言位置
            real_seer_id: 真预言家ID（倒钩狼需要）

        Returns:
            发言内容
        """
        if self.strategy == WerewolfStrategy.HARD_JUMP:
            return self.generate_hard_jump_speech(round_num)
        elif self.strategy == WerewolfStrategy.DEEP_WATER:
            return self.generate_deep_water_speech(round_num)
        elif self.strategy == WerewolfStrategy.WITCH_HUNT and real_seer_id:
            return self.generate_witch_hunt_speech(round_num, real_seer_id)
        elif self.strategy == WerewolfStrategy.SILENT:
            return "过。"
        else:
            return self.generate_deep_water_speech(round_num)

    # ============ 信息收集方法 ============

    def observe_speech(self, speaker_id: int, content: str, round_num: int):
        """观察玩家发言，收集信息"""
        self.speech_history.append({
            "round": round_num,
            "speaker": speaker_id,
            "content": content
        })

        # 识别可能的预言家
        if "预言家" in content and "查验" in content:
            if self.known_seer is None:
                self.known_seer = speaker_id
                logger.info(f"狼人 {self.player_name} 推测 {speaker_id} 是预言家")

        # 识别可能的女巫
        if "救了" in content or "毒了" in content:
            if self.known_witch is None:
                self.known_witch = speaker_id
                logger.info(f"狼人 {self.player_name} 推测 {speaker_id} 是女巫")

        # 识别可能的猎人
        if "开枪" in content or "带走" in content:
            if self.known_hunter is None:
                self.known_hunter = speaker_id
                logger.info(f"狼人 {self.player_name} 推测 {speaker_id} 是猎人")

        self.memory.append(WerewolfMemory(
            round_num=round_num,
            event_type="observe",
            content=f"{speaker_id}号发言: {content[:50]}..."
        ))

    def observe_death(self, dead_player_id: int, cause: str, round_num: int):
        """
        观察死亡事件，推断身份

        Args:
            dead_player_id: 死亡玩家ID
            cause: 死亡原因
            round_num: 当前轮次
        """
        # 如果死亡的是已知预言家，更新信息
        if dead_player_id == self.known_seer:
            self.known_seer = None

        self.memory.append(WerewolfMemory(
            round_num=round_num,
            event_type="death",
            content=f"{dead_player_id}号死于{cause}"
        ))

    # ============ 投票决策方法 ============

    def decide_vote_target(
            self,
            alive_players: List[int],
            round_num: int,
            agreed_target: Optional[int] = None
    ) -> Optional[int]:
        """
        决定投票目标

        投票策略：
        1. 优先执行狼队约定的投票目标
        2. 如果没有约定，则投给威胁最大的好人
        3. 深水狼跟随大流，避免引起怀疑
        4. 悍跳狼投给真预言家

        Args:
            alive_players: 存活玩家列表
            round_num: 当前轮次
            agreed_target: 狼队约定的目标

        Returns:
            投票目标ID
        """
        if not self.is_alive:
            return None

        # 如果有约定的投票目标
        if agreed_target and agreed_target in alive_players:
            return agreed_target

        # 根据策略决定
        if self.strategy == WerewolfStrategy.HARD_JUMP and self.known_seer:
            # 悍跳狼投给真预言家
            if self.known_seer in alive_players:
                return self.known_seer

        elif self.strategy == WerewolfStrategy.DEEP_WATER:
            # 深水狼跟随大多数人（不主动带节奏）
            # 实际实现中需要分析场上的发言倾向
            pass

        # 默认：投给威胁最大的（如果已知）
        if self.known_seer and self.known_seer in alive_players:
            return self.known_seer
        if self.known_witch and self.known_witch in alive_players:
            return self.known_witch

        return None

    # ============ 狼王特殊技能 ============

    def can_shoot_when_dead(self) -> bool:
        """死亡时是否可以开枪（狼王特殊技能）"""
        return self.wolf_type == WerewolfRole.WOLF_KING

    def can_explode(self) -> bool:
        """是否可以自爆带走一人（白狼王特殊技能）"""
        return self.wolf_type == WerewolfRole.WHITE_WOLF_KING

    # ============ 状态管理方法 ============

    def get_state_dict(self) -> Dict[str, Any]:
        """获取狼人当前状态"""
        return {
            "player_id": self.player_id,
            "player_name": self.player_name,
            "role_type": self.role_type,
            "wolf_type": self.wolf_type.value,
            "is_alive": self.is_alive,
            "teammates": list(self.teammates),
            "can_kill": self.can_kill,
            "kill_history": [k.to_dict() for k in self.kill_history],
            "pretend_role": self.pretend_role,
            "strategy": self.strategy.value,
            "is_seer_claimer": self.is_seer_claimer,
            "fake_checks": self.fake_checks,
            "known_seer": self.known_seer,
            "known_witch": self.known_witch,
            "known_hunter": self.known_hunter,
            "exposed_as_wolf": self.exposed_as_wolf,
            "survival_rounds": self.survival_rounds
        }

    def update_survival(self):
        """更新存活轮数"""
        self.survival_rounds += 1

    def reset_for_new_game(self):
        """重置狼人状态（用于新一局游戏）"""
        self.is_alive = True
        self.can_kill = True
        self.kill_history = []
        self.current_kill_target = None
        self.pretend_role = "villager"
        self.strategy = WerewolfStrategy.DEEP_WATER
        self.fake_checks = {}
        self.is_seer_claimer = False
        self.seer_claim_round = None
        self.self_kill_planned = False
        self.self_kill_round = None
        self.known_seer = None
        self.known_witch = None
        self.known_hunter = None
        self.vote_coordination = {}
        self.memory = []
        self.speech_history = []
        self.exposed_as_wolf = False
        self.survival_rounds = 0

        logger.info(f"狼人 {self.player_name}(ID:{self.player_id}) 状态已重置")

    def die(self):
        """狼人死亡"""
        self.is_alive = False
        logger.info(f"狼人 {self.player_name}(ID:{self.player_id}) 已死亡")

    def expose_as_wolf(self):
        """被查杀暴露"""
        self.exposed_as_wolf = True
        logger.info(f"狼人 {self.player_name}(ID:{self.player_id}) 被查杀")

    def __str__(self) -> str:
        kill_count = len(self.kill_history)
        return f"Werewolf({self.player_name}, ID:{self.player_id}, 刀人:{kill_count}, 策略:{self.strategy.value})"


# ============ 狼人团队管理器 ============

class WerewolfTeamManager:
    """
    狼人团队管理器 - 管理所有狼人角色的团队协作
    """

    def __init__(self, team_id: int = 1):
        """
        初始化狼人团队管理器

        Args:
            team_id: 团队ID
        """
        self.team_id = team_id
        self.wolves: Dict[int, Werewolf] = {}
        self.team_chat_log: List[Dict] = []  # 团队密谋日志
        self.current_round = 0

    def register_wolf(self, wolf: Werewolf) -> None:
        """注册狼人角色"""
        self.wolves[wolf.player_id] = wolf
        logger.info(f"狼人 {wolf.player_name} 已注册到团队 {self.team_id}")

    def setup_team(self):
        """设置团队关系（在所有狼人注册后调用）"""
        wolf_ids = list(self.wolves.keys())
        for wolf in self.wolves.values():
            teammates = [wid for wid in wolf_ids if wid != wolf.player_id]
            wolf.set_teammates(teammates)

        logger.info(f"狼人团队 {self.team_id} 已建立，成员: {wolf_ids}")

    def get_alive_wolves(self) -> List[Werewolf]:
        """获取存活的狼人"""
        return [w for w in self.wolves.values() if w.is_alive]

    def get_alive_wolf_ids(self) -> List[int]:
        """获取存活的狼人ID列表"""
        return [w.player_id for w in self.wolves.values() if w.is_alive]

    def is_any_wolf_alive(self) -> bool:
        """是否还有狼人存活"""
        return len(self.get_alive_wolves()) > 0

    def team_chat(self, sender_id: int, message: str, round_num: int):
        """狼队密谋"""
        self.team_chat_log.append({
            "round": round_num,
            "sender": sender_id,
            "message": message,
            "timestamp": datetime.now().isoformat()
        })

        # 广播给所有狼人
        for wolf in self.wolves.values():
            wolf.teammate_chat(message, round_num)

        logger.info(f"狼队密谋 (Round {round_num}): {sender_id}号: {message[:50]}")

    def coordinate_vote(self, round_num: int, target_id: int):
        """协调所有狼人统一投票"""
        for wolf in self.wolves.values():
            wolf.coordinate_vote(round_num, target_id)

        logger.info(f"狼队协调投票: Round {round_num} 统一投 {target_id}号")

    def get_consensus_kill_target(
            self,
            alive_players: List[int],
            player_roles: Dict[int, Optional[str]],
            round_num: int
    ) -> Tuple[Optional[int], bool]:
        """
        通过狼队投票决定刀人目标

        Returns:
            (目标ID, 是否自刀)
        """
        alive_wolves = self.get_alive_wolves()
        if not alive_wolves:
            return None, False

        # 收集每个狼人的刀人建议
        suggestions = []
        for wolf in alive_wolves:
            target, is_self_kill = wolf.decide_kill_target(alive_players, player_roles, round_num)
            if target is not None:
                suggestions.append((target, is_self_kill))

        if not suggestions:
            return None, False

        # 投票决定（简单多数）
        from collections import Counter
        target_counter = Counter([s[0] for s in suggestions])
        most_common_target = target_counter.most_common(1)[0][0]

        # 检查是否有狼人想自刀
        self_kill_votes = [s for s in suggestions if s[1]]
        is_self_kill = len(self_kill_votes) > len(suggestions) / 2

        return most_common_target, is_self_kill

    def record_kill(self, target_id: int, round_num: int, success: bool):
        """记录狼队共同的刀人结果"""
        for wolf in self.wolves.values():
            if wolf.can_kill and wolf.is_alive:
                wolf.perform_kill(target_id, round_num, success)

    def reset_all_night_actions(self):
        """重置所有狼人的夜间行动"""
        for wolf in self.wolves.values():
            if wolf.is_alive:
                wolf.reset_night_action()

    def get_all_wolf_states(self) -> Dict[int, Dict]:
        """获取所有狼人的状态"""
        return {pid: wolf.get_state_dict() for pid, wolf in self.wolves.items()}

    def reset_all(self):
        """重置所有狼人状态"""
        for wolf in self.wolves.values():
            wolf.reset_for_new_game()
        self.team_chat_log = []
        self.current_round = 0


# ============ 示例使用 ============

if __name__ == "__main__":
    # 创建狼人角色
    wolf1 = Werewolf(player_id=2, player_name="暗夜猎手", wolf_type=WerewolfRole.COMMON)
    wolf2 = Werewolf(player_id=4, player_name="血色玫瑰", wolf_type=WerewolfRole.COMMON)
    wolf3 = Werewolf(player_id=6, player_name="孤狼", wolf_type=WerewolfRole.WOLF_KING)

    # 创建团队管理器
    team_manager = WerewolfTeamManager(team_id=1)
    team_manager.register_wolf(wolf1)
    team_manager.register_wolf(wolf2)
    team_manager.register_wolf(wolf3)
    team_manager.setup_team()

    print(f"狼人1: {wolf1}")
    print(f"狼人2: {wolf2}")
    print(f"狼人3: {wolf3}")

    # 模拟夜间流程
    print("\n=== 模拟对局 ===")
    round_num = 1

    # 设置策略
    wolf1.set_strategy(WerewolfStrategy.HARD_JUMP)  # 悍跳狼
    wolf2.set_strategy(WerewolfStrategy.DEEP_WATER)  # 深水狼
    wolf3.set_strategy(WerewolfStrategy.WITCH_HUNT)  # 倒钩狼

    # 悍跳狼设置假查验
    wolf1.set_fake_check(target_id=5, result="wolf")  # 查杀5号

    # 生成发言
    print(f"\n悍跳狼发言: {wolf1.generate_hard_jump_speech(round_num)}")
    print(f"深水狼发言: {wolf2.generate_deep_water_speech(round_num)}")
    print(f"倒钩狼发言: {wolf3.generate_witch_hunt_speech(round_num, real_seer_id=1)}")

    # 狼队协调决定刀人目标
    alive_players = [1, 2, 3, 4, 5, 6]
    player_roles = {1: "seer", 3: "witch", 5: "villager"}

    target, is_self_kill = team_manager.get_consensus_kill_target(alive_players, player_roles, round_num)
    print(f"\n狼队决定刀人: {'自刀' if is_self_kill else f'刀{target}号'}")

    # 执行刀人
    if target:
        team_manager.record_kill(target, round_num, success=True)

    # 查看状态
    print(f"\n狼人1状态: {wolf1.get_state_dict()}")
    print(f"\n团队存活狼人: {team_manager.get_alive_wolf_ids()}")

    # 重置夜间行动
    team_manager.reset_all_night_actions()
    print(f"\n重置后刀人状态: can_kill={wolf1.can_kill}")