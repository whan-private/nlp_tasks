"""
狼人杀游戏 - 猎人角色模块
猎人是好人阵营的强神，拥有死亡时开枪带人的威慑能力
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


class DeathCause(Enum):
    """死亡原因枚举"""
    WOLF_KILL = "wolf_kill"  # 狼人刀死
    VOTE_OUT = "vote_out"  # 投票放逐
    WITCH_POISON = "witch_poison"  # 女巫毒死
    HUNTER_SHOT = "hunter_shot"  # 猎人开枪带走
    UNKNOWN = "unknown"  # 未知


class HunterSkillStatus(Enum):
    """猎人技能状态"""
    AVAILABLE = "available"  # 技能可用
    USED = "used"  # 已使用（开过枪）
    TRIGGERED = "triggered"  # 已触发（等待开枪）
    DISABLED = "disabled"  # 失效（被毒死不能开枪）


class HunterStrategy(Enum):
    """猎人策略类型"""
    CONSERVATIVE = "conservative"  # 保守：不轻易开枪
    AGGRESSIVE = "aggressive"  # 激进：怀疑就开枪
    RATIONAL = "rational"  # 理性：基于逻辑开枪
    SILENT = "silent"  # 沉默：隐藏身份


@dataclass
class HunterShotRecord:
    """猎人开枪记录"""
    round_num: int
    shooter_id: int
    shooter_name: str
    target_id: int
    target_name: str
    death_cause: DeathCause  # 猎人自己的死因
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "round": self.round_num,
            "shooter": self.shooter_id,
            "target": self.target_id,
            "death_cause": self.death_cause.value,
            "time": self.timestamp.isoformat()
        }


@dataclass
class HunterMemory:
    """猎人的记忆单元"""
    round_num: int
    event_type: str  # 'shot', 'speech', 'vote', 'death', 'suspicion'
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


class Hunter:
    """
    猎人角色类

    猎人是好人阵营的强神，拥有强大的反杀能力。
    猎人的核心价值在于：
    1. 威慑狼人，使其不敢轻易对跳或票猎人
    2. 死亡时带走一名玩家，实现一换一
    3. 通过开枪信息帮助好人判断局势
    4. 存活时作为潜在的投票力量

    重要规则：
    - 被狼刀死或被投票放逐时可以开枪
    - 被女巫毒死时不能开枪
    - 开枪后技能失效
    - 可以选择不开枪

    属性说明：
    - player_id: 玩家ID
    - player_name: 玩家名称
    - is_alive: 是否存活
    - skill_status: 技能状态
    - has_shot: 是否已经开过枪
    - shot_history: 开枪历史记录
    - suspected_targets: 怀疑的目标列表
    - trust_network: 对其他玩家的信任度
    - death_cause_when_dying: 死亡时的死因（用于判断能否开枪）
    - will_shoot_when_dead: 死亡时是否决定开枪
    - chosen_target_when_dead: 死亡时选中的开枪目标
    """

    def __init__(
            self,
            player_id: int,
            player_name: str,
            can_choose_not_shoot: bool = True  # 是否可以选择不开枪
    ):
        """
        初始化猎人角色

        Args:
            player_id: 玩家ID
            player_name: 玩家名称
            can_choose_not_shoot: 是否可以选择不开枪（默认True）
        """
        self.player_id = player_id
        self.player_name = player_name
        self.role_type = "hunter"
        self.is_alive = True

        # 技能状态
        self.skill_status = HunterSkillStatus.AVAILABLE
        self.has_shot = False
        self.can_choose_not_shoot = can_choose_not_shoot

        # 开枪记录
        self.shot_history: List[HunterShotRecord] = []
        self.total_shots = 0
        self.successful_shots = 0  # 成功带走人数

        # 死亡相关信息
        self.death_cause_when_dying: Optional[DeathCause] = None
        self.will_shoot_when_dead: bool = False
        self.chosen_target_when_dead: Optional[int] = None
        self.death_round: Optional[int] = None

        # 认知状态
        self.suspected_targets: Dict[int, float] = {}  # 怀疑度 {player_id: score 0-1}
        self.trust_scores: Dict[int, float] = {}  # 信任度 {player_id: score 0-1}
        self.known_wolves: Set[int] = set()  # 确认的狼人
        self.known_good_players: Set[int] = set()  # 确认的好人

        # 策略配置
        self.strategy = HunterStrategy.RATIONAL
        self.is_hidden = True  # 是否隐藏身份（不主动暴露）

        # 记忆系统
        self.memory: List[HunterMemory] = []
        self.speech_history: List[Dict] = []
        self.vote_history: List[Dict] = []

        # 游戏信息
        self.known_seer: Optional[int] = None
        self.known_witch: Optional[int] = None

        logger.info(f"猎人 {player_name}(ID:{player_id}) 初始化完成 - 可弃枪:{can_choose_not_shoot}")

    # ============ 技能方法 ============

    def can_shoot_on_death(self, death_cause: DeathCause) -> bool:
        """
        判断死亡时是否可以开枪

        规则：
        - 被狼刀死：可以开枪 ✓
        - 被投票放逐：可以开枪 ✓
        - 被女巫毒死：不能开枪 ✗
        - 已经开过枪：不能开枪 ✗

        Args:
            death_cause: 死亡原因

        Returns:
            是否可以开枪
        """
        if self.skill_status != HunterSkillStatus.AVAILABLE:
            return False

        if self.has_shot:
            return False

        # 被女巫毒死不能开枪
        if death_cause == DeathCause.WITCH_POISON:
            logger.info(f"猎人 {self.player_name} 被毒死，无法开枪")
            return False

        # 被狼刀死或投票放逐可以开枪
        if death_cause in [DeathCause.WOLF_KILL, DeathCause.VOTE_OUT]:
            return True

        return False

    def decide_shoot_on_death(
            self,
            alive_players: List[int],
            death_cause: DeathCause,
            round_num: int
    ) -> Tuple[bool, Optional[int]]:
        """
        决定死亡时是否开枪以及开枪目标

        决策逻辑：
        1. 保守策略：只有确认是狼人才开枪
        2. 激进策略：只要怀疑就开枪
        3. 理性策略：基于怀疑度和局势判断

        Args:
            alive_players: 存活玩家列表
            death_cause: 死亡原因
            round_num: 当前轮次

        Returns:
            (是否开枪, 目标ID)
        """
        if not self.can_shoot_on_death(death_cause):
            return False, None

        # 过滤掉自己和已知的好人
        candidates = [p for p in alive_players if p != self.player_id]

        if not candidates:
            return False, None

        # 根据策略决定
        if self.strategy == HunterStrategy.CONSERVATIVE:
            # 保守策略：只有确认是狼人才开枪
            if self.known_wolves:
                # 优先带走确认的狼人
                for wolf in self.known_wolves:
                    if wolf in candidates:
                        return True, wolf
            return False, None

        elif self.strategy == HunterStrategy.AGGRESSIVE:
            # 激进策略：带走怀疑度最高的
            if self.suspected_targets:
                most_suspected = max(
                    [(pid, score) for pid, score in self.suspected_targets.items() if pid in candidates],
                    key=lambda x: x[1],
                    default=(None, 0)
                )
                if most_suspected[0] is not None and most_suspected[1] > 0.5:
                    return True, most_suspected[0]
            # 没有特别怀疑的对象，随机带一个
            import random
            return True, random.choice(candidates)

        elif self.strategy == HunterStrategy.RATIONAL:
            # 理性策略：基于怀疑度阈值
            if self.suspected_targets:
                # 找出怀疑度超过0.7的玩家
                high_suspicion = [
                    pid for pid, score in self.suspected_targets.items()
                    if pid in candidates and score > 0.7
                ]
                if high_suspicion:
                    # 带走怀疑度最高的
                    target = max(high_suspicion, key=lambda x: self.suspected_targets[x])
                    return True, target

            # 如果有确认的狼人
            if self.known_wolves:
                for wolf in self.known_wolves:
                    if wolf in candidates:
                        return True, wolf

            return False, None

        elif self.strategy == HunterStrategy.SILENT:
            # 沉默策略：不开枪，隐藏身份信息
            return False, None

        return False, None

    def shoot(self, target_id: int, death_cause: DeathCause, round_num: int) -> HunterShotRecord:
        """
        执行开枪

        Args:
            target_id: 目标玩家ID
            death_cause: 猎人自己的死因
            round_num: 当前轮次

        Returns:
            开枪记录
        """
        if self.has_shot:
            raise ValueError(f"猎人 {self.player_name} 已经开过枪了")

        record = HunterShotRecord(
            round_num=round_num,
            shooter_id=self.player_id,
            shooter_name=self.player_name,
            target_id=target_id,
            target_name=f"Player_{target_id}",
            death_cause=death_cause
        )

        self.shot_history.append(record)
        self.has_shot = True
        self.skill_status = HunterSkillStatus.USED
        self.total_shots += 1
        self.successful_shots += 1

        # 记录记忆
        self.memory.append(HunterMemory(
            round_num=round_num,
            event_type="shot",
            content=f"死亡时开枪带走 {target_id} 号玩家，死因: {death_cause.value}"
        ))

        logger.info(f"猎人 {self.player_name} 在{round_num}轮死亡时开枪带走 {target_id} 号玩家")

        return record

    def choose_not_shoot(self, death_cause: DeathCause, round_num: int):
        """
        选择不开枪

        Args:
            death_cause: 死亡原因
            round_num: 当前轮次
        """
        self.will_shoot_when_dead = False
        self.skill_status = HunterSkillStatus.DISABLED

        self.memory.append(HunterMemory(
            round_num=round_num,
            event_type="shot",
            content=f"死亡时选择不开枪，死因: {death_cause.value}"
        ))

        logger.info(f"猎人 {self.player_name} 在{round_num}轮死亡时选择不开枪")

    # ============ 认知与推理方法 ============

    def observe_speech(self, speaker_id: int, content: str, round_num: int):
        """
        观察玩家发言，更新怀疑度

        Args:
            speaker_id: 发言者ID
            content: 发言内容
            round_num: 当前轮次
        """
        self.speech_history.append({
            "round": round_num,
            "speaker": speaker_id,
            "content": content
        })

        # 分析发言，更新怀疑度
        suspicion_change = self._analyze_speech_suspicion(content, speaker_id)

        # 更新怀疑度
        if speaker_id not in self.suspected_targets:
            self.suspected_targets[speaker_id] = 0.5
        self.suspected_targets[speaker_id] = max(0, min(1,
                                                        self.suspected_targets[speaker_id] + suspicion_change))

        # 更新信任度（负相关）
        if speaker_id not in self.trust_scores:
            self.trust_scores[speaker_id] = 0.5
        self.trust_scores[speaker_id] = max(0, min(1,
                                                   self.trust_scores[speaker_id] - suspicion_change * 0.5))

        # 识别跳身份
        if "猎人" in content and ("我是猎人" in content or "开枪" in content):
            if self.is_hidden:
                # 其他人跳猎人，可能是狼人冒充
                self.suspected_targets[speaker_id] = min(1,
                                                         self.suspected_targets.get(speaker_id, 0.5) + 0.2)

        self.memory.append(HunterMemory(
            round_num=round_num,
            event_type="speech",
            content=f"{speaker_id}号发言: {content[:50]}..."
        ))

    def _analyze_speech_suspicion(self, content: str, speaker_id: int) -> float:
        """
        分析发言，计算怀疑度变化

        Returns:
            怀疑度变化值（正数增加怀疑，负数减少怀疑）
        """
        change = 0.0

        # 正向信号（减少怀疑）
        if "我是好人" in content:
            change -= 0.05
        if "逻辑" in content:
            change -= 0.03
        if "分析" in content:
            change -= 0.03

        # 负向信号（增加怀疑）
        if "划水" in content or "不知道" in content:
            change += 0.08
        if "跟票" in content:
            change += 0.05
        if "过麦" in content and len(content) < 10:
            change += 0.1  # 简短过麦，划水嫌疑

        # 矛盾信号（需要结合历史判断，简化版）
        # 实际应用中可以用LLM分析逻辑一致性

        return change

    def observe_death(self, dead_player_id: int, cause: DeathCause, round_num: int):
        """
        观察死亡事件

        Args:
            dead_player_id: 死亡玩家ID
            cause: 死亡原因
            round_num: 当前轮次
        """
        # 如果死亡的是怀疑对象，调整信任度
        if dead_player_id in self.suspected_targets:
            if cause == DeathCause.WOLF_KILL:
                # 被狼刀死，可能是好人
                self.suspected_targets[dead_player_id] = max(0,
                                                             self.suspected_targets[dead_player_id] - 0.3)
                self.known_good_players.add(dead_player_id)
            elif cause == DeathCause.VOTE_OUT:
                # 被投票放逐，如果之前怀疑度高，说明判断正确
                if self.suspected_targets.get(dead_player_id, 0) > 0.6:
                    self.known_wolves.add(dead_player_id)

        self.memory.append(HunterMemory(
            round_num=round_num,
            event_type="death",
            content=f"{dead_player_id}号死于{cause.value}"
        ))

    def observe_vote(self, voter_id: int, target_id: int, round_num: int):
        """
        观察投票行为

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

        # 分析投票行为，更新怀疑度
        # 如果某人总是跟票，增加怀疑
        # 简化实现，完整版需要分析投票模式

        self.memory.append(HunterMemory(
            round_num=round_num,
            event_type="vote",
            content=f"{voter_id}号投票给{target_id}号"
        ))

    # ============ 决策方法 ============

    def decide_vote_target(
            self,
            alive_players: List[int],
            round_num: int,
            seer_check_result: Optional[Tuple[int, str]] = None
    ) -> Optional[int]:
        """
        决定投票目标

        猎人的投票策略：
        1. 优先投给确认的狼人
        2. 其次投给怀疑度最高的玩家
        3. 跟随预言家的查杀

        Args:
            alive_players: 存活玩家列表
            round_num: 当前轮次
            seer_check_result: (目标ID, 结果) 预言家的查验结果

        Returns:
            投票目标ID
        """
        if not self.is_alive:
            return None

        # 过滤掉自己
        candidates = [p for p in alive_players if p != self.player_id]

        if not candidates:
            return None

        # 优先投给确认的狼人
        for wolf in self.known_wolves:
            if wolf in candidates:
                return wolf

        # 其次，跟随预言家的查杀
        if seer_check_result:
            target, result = seer_check_result
            if result == "wolf" and target in candidates:
                return target

        # 最后，投给怀疑度最高的
        if self.suspected_targets:
            # 找出存活且怀疑度最高的
            alive_suspected = [
                (pid, score) for pid, score in self.suspected_targets.items()
                if pid in candidates
            ]
            if alive_suspected:
                most_suspected = max(alive_suspected, key=lambda x: x[1])
                if most_suspected[1] > 0.6:  # 怀疑度阈值
                    return most_suspected[0]

        return None

    def decide_reveal_identity(self, round_num: int, situation: str) -> bool:
        """
        决定是否暴露猎人身份

        暴露时机：
        - 被严重怀疑时
        - 需要带队时
        - 死前遗言

        Args:
            round_num: 当前轮次
            situation: 当前局势 ('suspected', 'leading', 'dying')

        Returns:
            是否暴露身份
        """
        if situation == "dying":
            # 死前可以暴露
            return True

        if situation == "suspected":
            # 被严重怀疑时暴露自证
            return True

        if situation == "leading":
            # 需要带队时，如果已经确定狼人可以暴露
            if len(self.known_wolves) >= 1:
                return True

        return False

    def generate_speech(self, round_num: int, is_dying: bool = False) -> str:
        """
        生成发言内容

        Args:
            round_num: 当前轮次
            is_dying: 是否是遗言

        Returns:
            发言内容
        """
        if is_dying:
            return self._generate_death_speech(round_num)

        if self.is_hidden:
            return self._generate_hidden_speech(round_num)
        else:
            return self._generate_exposed_speech(round_num)

    def _generate_hidden_speech(self, round_num: int) -> str:
        """生成隐藏身份的发言"""
        speeches = [
            "我是好人，过。",
            "平民一个，听预言家的。",
            "我是村民，没什么信息。",
            "好人，跟警长投票。"
        ]

        # 如果有怀疑对象，可以适当表达
        if self.suspected_targets:
            high_suspicion = [
                pid for pid, score in self.suspected_targets.items()
                if score > 0.7
            ]
            if high_suspicion:
                target = high_suspicion[0]
                return f"我觉得{target}号玩家行为可疑，这一轮可能会投他。过。"

        import random
        return random.choice(speeches)

    def _generate_exposed_speech(self, round_num: int) -> str:
        """生成暴露身份的发言"""
        speech_parts = ["我是猎人，"]

        if self.suspected_targets:
            high_suspicion = [
                pid for pid, score in self.suspected_targets.items()
                if score > 0.7
            ]
            if high_suspicion:
                speech_parts.append(f"我觉得{high_suspicion[0]}号是狼人，")

        if self.known_wolves:
            speech_parts.append(f"我确定{list(self.known_wolves)[0]}号是狼人，")

        speech_parts.append("谁要是敢票我，我就带谁走。过。")

        return "".join(speech_parts)

    def _generate_death_speech(self, round_num: int) -> str:
        """生成死亡遗言"""
        speech_parts = ["我是猎人，"]

        if self.will_shoot_when_dead and self.chosen_target_when_dead:
            speech_parts.append(f"我会带走{self.chosen_target_when_dead}号玩家，")
            if self.chosen_target_when_dead in self.known_wolves:
                speech_parts.append("因为他是狼人。")
            else:
                speech_parts.append("我怀疑他是狼人。")
        else:
            speech_parts.append("我选择不开枪，")
            if self.known_wolves:
                speech_parts.append(f"我怀疑{list(self.known_wolves)[0]}号是狼人，但我不确定。")
            else:
                speech_parts.append("因为没有确定的目标。")

        speech_parts.append("过。")

        return "".join(speech_parts)

    # ============ 状态管理方法 ============

    def set_death_info(self, death_cause: DeathCause, round_num: int):
        """
        设置死亡信息（在猎人死亡时调用）

        Args:
            death_cause: 死亡原因
            round_num: 死亡轮次
        """
        self.death_cause_when_dying = death_cause
        self.death_round = round_num
        self.is_alive = False

        # 判断是否可以开枪并决定
        if self.can_shoot_on_death(death_cause):
            # 需要外部调用 decide_shoot_on_death 来决定
            self.skill_status = HunterSkillStatus.TRIGGERED
        else:
            self.skill_status = HunterSkillStatus.DISABLED

        logger.info(f"猎人 {self.player_name} 在{round_num}轮死亡，死因: {death_cause.value}")

    def get_state_dict(self) -> Dict[str, Any]:
        """获取猎人当前状态"""
        return {
            "player_id": self.player_id,
            "player_name": self.player_name,
            "role_type": self.role_type,
            "is_alive": self.is_alive,
            "skill_status": self.skill_status.value,
            "has_shot": self.has_shot,
            "total_shots": self.total_shots,
            "successful_shots": self.successful_shots,
            "shot_history": [s.to_dict() for s in self.shot_history],
            "suspected_targets": self.suspected_targets.copy(),
            "trust_scores": self.trust_scores.copy(),
            "known_wolves": list(self.known_wolves),
            "known_good_players": list(self.known_good_players),
            "strategy": self.strategy.value,
            "is_hidden": self.is_hidden,
            "death_cause": self.death_cause_when_dying.value if self.death_cause_when_dying else None,
            "death_round": self.death_round
        }

    def confirm_wolf(self, player_id: int):
        """确认某玩家是狼人"""
        self.known_wolves.add(player_id)
        if player_id in self.suspected_targets:
            self.suspected_targets[player_id] = 1.0
        logger.info(f"猎人 {self.player_name} 确认 {player_id} 是狼人")

    def confirm_good(self, player_id: int):
        """确认某玩家是好人"""
        self.known_good_players.add(player_id)
        if player_id in self.suspected_targets:
            del self.suspected_targets[player_id]
        if player_id in self.trust_scores:
            self.trust_scores[player_id] = 1.0
        logger.info(f"猎人 {self.player_name} 确认 {player_id} 是好人")

    def reset_for_new_game(self):
        """重置猎人状态（用于新一局游戏）"""
        self.is_alive = True
        self.skill_status = HunterSkillStatus.AVAILABLE
        self.has_shot = False
        self.shot_history = []
        self.total_shots = 0
        self.successful_shots = 0
        self.death_cause_when_dying = None
        self.will_shoot_when_dead = False
        self.chosen_target_when_dead = None
        self.death_round = None
        self.suspected_targets = {}
        self.trust_scores = {}
        self.known_wolves = set()
        self.known_good_players = set()
        self.memory = []
        self.speech_history = []
        self.vote_history = []
        self.known_seer = None
        self.known_witch = None

        logger.info(f"猎人 {self.player_name}(ID:{self.player_id}) 状态已重置")

    def set_strategy(self, strategy: HunterStrategy):
        """设置猎人策略"""
        self.strategy = strategy
        logger.info(f"猎人 {self.player_name} 切换策略为 {strategy.value}")

    def reveal_identity(self):
        """暴露猎人身份"""
        self.is_hidden = False
        logger.info(f"猎人 {self.player_name} 暴露身份")

    def __str__(self) -> str:
        return f"Hunter({self.player_name}, ID:{self.player_id}, 存活:{self.is_alive}, 已开枪:{self.has_shot})"


# ============ 猎人管理器 ============

class HunterManager:
    """
    猎人管理器 - 管理猎人角色和开枪流程
    """

    def __init__(self):
        self.hunters: Dict[int, Hunter] = {}
        self.pending_shot: Optional[Hunter] = None  # 等待开枪的猎人

    def register_hunter(self, hunter: Hunter) -> None:
        """注册猎人角色"""
        self.hunters[hunter.player_id] = hunter
        logger.info(f"猎人 {hunter.player_name} 已注册")

    def get_hunter(self, player_id: int) -> Optional[Hunter]:
        """根据玩家ID获取猎人对象"""
        return self.hunters.get(player_id)

    def get_alive_hunter(self) -> Optional[Hunter]:
        """获取存活的猎人"""
        for hunter in self.hunters.values():
            if hunter.is_alive:
                return hunter
        return None

    def get_all_hunters(self) -> List[Hunter]:
        """获取所有猎人"""
        return list(self.hunters.values())

    def handle_hunter_death(
            self,
            hunter_id: int,
            death_cause: DeathCause,
            round_num: int,
            alive_players: List[int]
    ) -> Tuple[bool, Optional[int]]:
        """
        处理猎人死亡，决定是否开枪

        Args:
            hunter_id: 猎人ID
            death_cause: 死亡原因
            round_num: 当前轮次
            alive_players: 存活玩家列表

        Returns:
            (是否开枪, 目标ID)
        """
        hunter = self.get_hunter(hunter_id)
        if not hunter:
            return False, None

        # 设置死亡信息
        hunter.set_death_info(death_cause, round_num)

        # 如果猎人已死亡且可以开枪
        if not hunter.is_alive and hunter.can_shoot_on_death(death_cause):
            self.pending_shot = hunter
            # 决定开枪目标
            will_shoot, target = hunter.decide_shoot_on_death(alive_players, death_cause, round_num)
            hunter.will_shoot_when_dead = will_shoot
            hunter.chosen_target_when_dead = target

            if will_shoot and target:
                hunter.shoot(target, death_cause, round_num)
                return True, target

        return False, None

    def clear_pending_shot(self):
        """清除等待开枪的猎人"""
        self.pending_shot = None

    def get_all_hunter_states(self) -> Dict[int, Dict]:
        """获取所有猎人的状态"""
        return {pid: hunter.get_state_dict() for pid, hunter in self.hunters.items()}

    def reset_all(self):
        """重置所有猎人状态"""
        for hunter in self.hunters.values():
            hunter.reset_for_new_game()
        self.pending_shot = None


# ============ 示例使用 ============

if __name__ == "__main__":
    # 创建猎人角色
    hunter1 = Hunter(player_id=7, player_name="猎手阿七", can_choose_not_shoot=True)
    hunter2 = Hunter(player_id=8, player_name="神枪手", can_choose_not_shoot=False)

    # 设置策略
    hunter1.set_strategy(HunterStrategy.RATIONAL)
    hunter2.set_strategy(HunterStrategy.AGGRESSIVE)

    print(f"猎人1: {hunter1}")
    print(f"猎人2: {hunter2}")

    # 模拟游戏过程
    print("\n=== 模拟对局 ===")
    round_num = 2

    # 观察发言
    hunter1.observe_speech(1, "我是预言家，昨晚查了3号是狼人！", round_num)
    hunter1.observe_speech(3, "我是好人，1号在乱说，我才是真预言家！", round_num)
    hunter1.observe_speech(5, "划水过麦", round_num)

    print(f"\n怀疑度: {hunter1.suspected_targets}")
    print(f"信任度: {hunter1.trust_scores}")

    # 决定投票
    vote_target = hunter1.decide_vote_target([1, 2, 3, 4, 5, 6, 7], round_num, (3, "wolf"))
    print(f"\n投票目标: {vote_target}号")

    # 模拟猎人死亡
    print("\n=== 模拟猎人死亡 ===")
    alive_players = [1, 2, 3, 4, 5, 6, 8]

    # 猎人1被狼刀死
    will_shoot, target = hunter1.decide_shoot_on_death(alive_players, DeathCause.WOLF_KILL, round_num)
    print(f"猎人1被刀死，是否开枪: {will_shoot}, 目标: {target}")

    if will_shoot and target:
        hunter1.shoot(target, DeathCause.WOLF_KILL, round_num)

    # 查看状态
    print(f"\n猎人1最终状态: {hunter1.get_state_dict()}")

    # 使用管理器
    print("\n=== 使用管理器 ===")
    manager = HunterManager()
    manager.register_hunter(hunter1)
    manager.register_hunter(hunter2)

    # 模拟猎人2被投票放逐
    will_shoot2, target2 = manager.handle_hunter_death(8, DeathCause.VOTE_OUT, round_num, alive_players)
    print(f"猎人2被投票放逐，是否开枪: {will_shoot2}, 目标: {target2}")

    print(f"\n所有猎人状态: {manager.get_all_hunter_states()}")