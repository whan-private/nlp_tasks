"""
狼人杀游戏 - 平民角色模块
平民是好人阵营的基础成员，没有特殊技能，依靠逻辑推理和发言帮助阵营获胜
"""

from enum import Enum
from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class VillagerBelief(Enum):
    """平民对场上局势的信念状态"""
    NEUTRAL = "neutral"  # 中立/无明确立场
    TRUST_P1 = "trust_p1"  # 信任预言家1号
    TRUST_P2 = "trust_p2"  # 信任预言家2号
    SUSPECT_SOMEONE = "suspect"  # 怀疑某人
    CONFUSED = "confused"  # 困惑/摇摆不定


class VotingIntent(Enum):
    """投票意图"""
    FOLLOW_PREDICTOR = "follow_predictor"  # 跟随预言家
    FOLLOW_SHERIFF = "follow_sheriff"  # 跟随警长
    SELF_JUDGMENT = "self_judgment"  # 自主判断
    RANDOM = "random"  # 随机（极少情况）


@dataclass
class VillagerMemory:
    """平民的记忆单元"""
    round_num: int
    event_type: str  # 'speech', 'vote', 'death', 'claim'
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SuspectRecord:
    """怀疑记录"""
    player_id: int
    suspicion_score: float  # 0-1，越高越可疑
    reasons: List[str]
    update_round: int


class Villager:
    """
    平民角色类

    平民是好人阵营的基础成员，没有任何特殊技能。
    平民的核心价值在于：
    1. 通过投票行使民主权力
    2. 通过发言提供信息和分析
    3. 掩护神职角色，避免神职过早暴露
    4. 作为好人的基础票仓

    属性说明：
    - player_id: 玩家ID
    - player_name: 玩家名称
    - is_alive: 是否存活
    - has_voted_today: 今日是否已投票
    - current_vote_target: 当前投票目标
    - belief_state: 当前信念状态
    - suspects: 怀疑对象字典
    - memory: 记忆存储
    - trust_network: 信任网络（对每个玩家的信任度）
    - speech_log: 发言历史
    """

    def __init__(
            self,
            player_id: int,
            player_name: str,
            is_villager: bool = True  # 平民本色，但可用于子类扩展
    ):
        """
        初始化平民角色

        Args:
            player_id: 玩家ID
            player_name: 玩家名称
            is_villager: 是否为平民（用于兼容其他村民类角色）
        """
        self.player_id = player_id
        self.player_name = player_name
        self.role_type = "villager"  # 角色类型标识
        self.is_villager = is_villager
        self.is_alive = True

        # 投票相关
        self.has_voted_today = False
        self.current_vote_target: Optional[int] = None
        self.vote_history: List[Dict[int, int]] = []  # 每轮的投票记录 {round: target_id}

        # 认知状态
        self.belief_state = VillagerBelief.NEUTRAL
        self.confidence_level = 0.5  # 自信程度 0-1
        self.suspects: Dict[int, SuspectRecord] = {}  # 怀疑对象
        self.trust_scores: Dict[int, float] = {}  # 信任度评分 0-1

        # 已知身份信息（平民知道自己是好人，但不知道其他任何人的身份）
        self.known_identities: Dict[int, str] = {}  # {player_id: role_type} 仅记录已公开的身份
        self.self_claimed_predictors: Set[int] = set()  # 自称预言家的玩家

        # 记忆系统
        self.memory: List[VillagerMemory] = []
        self.speech_history: List[Dict] = []  # 发言历史
        self.death_info: Dict[int, str] = {}  # 死亡信息 {player_id: death_cause}

        # 策略配置
        self.voting_strategy = VotingIntent.SELF_JUDGMENT
        self.is_conservative = True  # 是否保守（保守平民会尽量隐藏自己）

        logger.info(f"平民 {player_name}(ID:{player_id}) 初始化完成")

    # ============ 基础属性方法 ============

    def is_eligible_to_vote(self) -> bool:
        """检查是否有投票资格"""
        return self.is_alive and not self.has_voted_today

    def reset_daily_vote(self):
        """重置每日投票状态"""
        self.has_voted_today = False
        self.current_vote_target = None

    def record_vote(self, round_num: int, target_id: int):
        """
        记录投票

        Args:
            round_num: 轮次
            target_id: 投票目标
        """
        self.has_voted_today = True
        self.current_vote_target = target_id
        self.vote_history.append({round_num: target_id})
        logger.info(f"平民 {self.player_name} 在{round_num}轮投票给 {target_id} 号玩家")

    # ============ 认知与推理方法 ============

    def observe_speech(self, speaker_id: int, speech_content: str, round_num: int):
        """
        观察玩家发言

        Args:
            speaker_id: 发言者ID
            speech_content: 发言内容
            round_num: 当前轮次
        """
        # 存储发言记录
        self.speech_history.append({
            "round": round_num,
            "speaker": speaker_id,
            "content": speech_content
        })

        # 分析发言内容，更新信任度
        self._analyze_speech_and_update_trust(speaker_id, speech_content, round_num)

        # 记录到记忆
        self.memory.append(VillagerMemory(
            round_num=round_num,
            event_type="speech",
            content=f"{speaker_id}号发言: {speech_content[:50]}..."
        ))

    def _analyze_speech_and_update_trust(self, speaker_id: int, content: str, round_num: int):
        """
        分析发言并更新信任度

        平民通过发言分析来判断玩家的可信度：
        - 逻辑一致性：前后发言是否矛盾
        - 信息量：是否提供了有价值的信息
        - 立场稳定性：是否频繁改变立场
        - 身份声明：是否跳预言家或声称神职
        """
        # 检查是否跳预言家
        if "预言家" in content or "我是预言家" in content or "查验" in content:
            self.self_claimed_predictors.add(speaker_id)
            if speaker_id not in self.known_identities:
                self.known_identities[speaker_id] = "claimed_seer"

        # 计算信任度变化（简化版，实际可用NLP模型）
        trust_change = self._calculate_trust_change(content, speaker_id)

        # 更新信任度
        if speaker_id not in self.trust_scores:
            self.trust_scores[speaker_id] = 0.5  # 初始中立
        self.trust_scores[speaker_id] = max(0, min(1, self.trust_scores[speaker_id] + trust_change))

        # 更新怀疑对象
        if self.trust_scores[speaker_id] < 0.3:
            if speaker_id not in self.suspects:
                self.suspects[speaker_id] = SuspectRecord(
                    player_id=speaker_id,
                    suspicion_score=1 - self.trust_scores[speaker_id],
                    reasons=[f"Round {round_num}: 发言可信度低"],
                    update_round=round_num
                )
            else:
                self.suspects[speaker_id].suspicion_score = 1 - self.trust_scores[speaker_id]
                self.suspects[speaker_id].reasons.append(f"Round {round_num}: 信任度下降")
                self.suspects[speaker_id].update_round = round_num

    def _calculate_trust_change(self, content: str, speaker_id: int) -> float:
        """
        计算信任度变化（简化版）

        实际应用中可接入LLM进行深度分析
        """
        trust_change = 0.0

        # 正向信号
        if "我认为" in content or "我觉得" in content:
            trust_change += 0.05  # 表达个人观点
        if "逻辑" in content:
            trust_change += 0.03  # 提及逻辑
        if "根据" in content:
            trust_change += 0.02  # 有依据

        # 负向信号
        if "我不知道" in content or "不清楚" in content:
            trust_change -= 0.05  # 信息不足
        if "划水" in content or "过麦" in content:
            trust_change -= 0.08  # 划水行为
        if "跟票" in content:
            trust_change -= 0.03  # 跟风

        return trust_change

    def observe_death(self, dead_player_id: int, cause: str, round_num: int):
        """
        观察死亡事件

        Args:
            dead_player_id: 死亡玩家ID
            cause: 死亡原因 ('wolf_kill', 'poison', 'vote', 'hunter_shot')
            round_num: 当前轮次
        """
        self.death_info[dead_player_id] = cause

        # 根据死亡原因更新对其他玩家的看法
        if cause == "wolf_kill":
            # 被狼杀的是好人（大概率）
            if dead_player_id in self.suspects:
                del self.suspects[dead_player_id]

        self.memory.append(VillagerMemory(
            round_num=round_num,
            event_type="death",
            content=f"{dead_player_id}号玩家死于{cause}"
        ))

    def observe_vote_result(self, voted_out_id: int, round_num: int):
        """
        观察投票结果

        Args:
            voted_out_id: 被放逐的玩家ID
            round_num: 当前轮次
        """
        # 如果投票出去的玩家是之前怀疑的对象，增加自信度
        if voted_out_id in self.suspects:
            self.confidence_level = min(1.0, self.confidence_level + 0.1)
            logger.info(f"平民 {self.player_name} 的怀疑得到验证，自信度提升至 {self.confidence_level}")

        self.memory.append(VillagerMemory(
            round_num=round_num,
            event_type="vote_result",
            content=f"{voted_out_id}号玩家被放逐"
        ))

    # ============ 决策方法 ============

    def decide_vote_target(
            self,
            alive_players: List[int],
            round_num: int,
            sheriff_id: Optional[int] = None
    ) -> Optional[int]:
        """
        决定投票目标

        平民的投票决策基于：
        1. 当前怀疑度最高的玩家
        2. 如果跟随警长/预言家策略，则投给他们指认的目标
        3. 自主判断的综合评分

        Args:
            alive_players: 存活玩家列表
            round_num: 当前轮次
            sheriff_id: 警长ID

        Returns:
            投票目标ID，None表示弃票
        """
        if not self.is_eligible_to_vote():
            return None

        # 过滤掉自己
        targets = [p for p in alive_players if p != self.player_id]

        if not targets:
            return None

        # 根据策略决定
        if self.voting_strategy == VotingIntent.FOLLOW_PREDICTOR:
            # 跟随可信的预言家
            trusted_predictor = self._get_most_trusted_predictor()
            if trusted_predictor and trusted_predictor in self.known_identities:
                # 需要从预言家的发言中获取查验目标（简化版）
                return self._get_predictor_target(trusted_predictor)

        elif self.voting_strategy == VotingIntent.FOLLOW_SHERIFF:
            if sheriff_id and sheriff_id != self.player_id:
                # 跟随警长投票（需要外部提供警长目标）
                pass

        # 默认：自主判断，投给最可疑的人
        return self._get_most_suspicious_target(targets)

    def _get_most_suspicious_target(self, candidates: List[int]) -> Optional[int]:
        """
        获取最可疑的投票目标

        Returns:
            最可疑的玩家ID
        """
        if not candidates:
            return None

        # 计算每个候选人的可疑度
        suspicion_scores = {}
        for pid in candidates:
            if pid in self.suspects:
                suspicion_scores[pid] = self.suspects[pid].suspicion_score
            else:
                # 默认可疑度基于信任度
                trust = self.trust_scores.get(pid, 0.5)
                suspicion_scores[pid] = 1 - trust

        if not suspicion_scores:
            return candidates[0]  # 没有信息时随机选一个

        # 返回可疑度最高的
        return max(suspicion_scores, key=suspicion_scores.get)

    def _get_most_trusted_predictor(self) -> Optional[int]:
        """
        获取最信任的预言家

        Returns:
            最信任的预言家ID
        """
        if not self.self_claimed_predictors:
            return None

        # 计算每个自称预言家的可信度
        trust_scores = {}
        for pid in self.self_claimed_predictors:
            trust_scores[pid] = self.trust_scores.get(pid, 0.5)

        if not trust_scores:
            return None

        return max(trust_scores, key=trust_scores.get)

    def _get_predictor_target(self, predictor_id: int) -> Optional[int]:
        """
        从预言家发言中获取查验目标（简化版）
        实际应用中需要解析发言内容
        """
        # 简化实现：从最近发言中查找
        for speech in reversed(self.speech_history):
            if speech["speaker"] == predictor_id:
                content = speech["content"]
                # 查找类似 "我查了X号" 的模式
                import re
                match = re.search(r'查了?(\d+)号', content)
                if match:
                    return int(match.group(1))
        return None

    # ============ 发言生成方法 ============

    def generate_speech(
            self,
            round_num: int,
            position: str,  # 'first', 'middle', 'last'
            alive_players: List[int]
    ) -> str:
        """
        生成发言内容

        平民的发言策略：
        - 保守平民：简短表态，不暴露身份
        - 主动平民：提供分析，引导投票
        - 划水平民：简单过麦（不推荐）

        Args:
            round_num: 当前轮次
            position: 发言位置
            alive_players: 存活玩家列表

        Returns:
            发言内容
        """
        # 第一轮发言通常简短
        if round_num == 1:
            return self._generate_first_round_speech(position)

        # 后期发言包含分析
        return self._generate_analysis_speech(round_num, position, alive_players)

    def _generate_first_round_speech(self, position: str) -> str:
        """生成第一轮发言"""
        if self.is_conservative:
            # 保守发言
            speeches = [
                "我是好人，过。",
                "平民一个，没啥信息，过。",
                "好人，听预言家怎么说。"
            ]
            import random
            return random.choice(speeches)
        else:
            # 主动发言
            return "我是好人，这一轮我会仔细听大家的发言，找出狼人的破绽。过。"

    def _generate_analysis_speech(
            self,
            round_num: int,
            position: str,
            alive_players: List[int]
    ) -> str:
        """生成分析发言"""
        speech_parts = []

        # 开场白
        speech_parts.append("我是好人。")

        # 分析怀疑对象
        if self.suspects:
            most_suspect = max(self.suspects.values(), key=lambda x: x.suspicion_score)
            speech_parts.append(f"我觉得{most_suspect.player_id}号玩家行为可疑，")
            if most_suspect.reasons:
                speech_parts.append(f"因为{most_suspect.reasons[-1]}。")

        # 表明立场
        if self.self_claimed_predictors:
            trusted = self._get_most_trusted_predictor()
            if trusted:
                speech_parts.append(f"我比较相信{trusted}号是预言家。")

        # 投票意向
        target = self._get_most_suspicious_target([p for p in alive_players if p != self.player_id])
        if target:
            speech_parts.append(f"这一轮我会投票给{target}号。")

        speech_parts.append("过。")

        return "".join(speech_parts)

    # ============ 状态管理方法 ============

    def get_state_dict(self) -> Dict[str, Any]:
        """获取平民当前状态"""
        return {
            "player_id": self.player_id,
            "player_name": self.player_name,
            "role_type": self.role_type,
            "is_alive": self.is_alive,
            "has_voted_today": self.has_voted_today,
            "vote_history": self.vote_history,
            "belief_state": self.belief_state.value,
            "confidence_level": self.confidence_level,
            "trust_scores": self.trust_scores.copy(),
            "suspects": {pid: record.suspicion_score for pid, record in self.suspects.items()},
            "known_identities": self.known_identities.copy(),
            "self_claimed_predictors": list(self.self_claimed_predictors),
            "voting_strategy": self.voting_strategy.value,
            "is_conservative": self.is_conservative
        }

    def reset_for_new_game(self):
        """重置平民状态（用于新一局游戏）"""
        self.is_alive = True
        self.has_voted_today = False
        self.current_vote_target = None
        self.vote_history = []
        self.belief_state = VillagerBelief.NEUTRAL
        self.confidence_level = 0.5
        self.suspects = {}
        self.trust_scores = {}
        self.known_identities = {}
        self.self_claimed_predictors = set()
        self.memory = []
        self.speech_history = []
        self.death_info = {}

        logger.info(f"平民 {self.player_name}(ID:{self.player_id}) 状态已重置")

    def die(self):
        """平民死亡"""
        self.is_alive = False
        logger.info(f"平民 {self.player_name}(ID:{self.player_id}) 已死亡")

    def __str__(self) -> str:
        return f"Villager({self.player_name}, ID:{self.player_id}, 存活:{self.is_alive})"


# ============ 平民管理器 ============

class VillagerManager:
    """
    平民管理器 - 管理所有平民角色
    """

    def __init__(self):
        self.villagers: Dict[int, Villager] = {}

    def register_villager(self, villager: Villager) -> None:
        """注册平民"""
        self.villagers[villager.player_id] = villager
        logger.info(f"平民 {villager.player_name} 已注册")

    def get_villager(self, player_id: int) -> Optional[Villager]:
        """获取平民对象"""
        return self.villagers.get(player_id)

    def get_alive_villagers(self) -> List[Villager]:
        """获取存活的平民"""
        return [v for v in self.villagers.values() if v.is_alive]

    def get_alive_villager_ids(self) -> List[int]:
        """获取存活的平民ID列表"""
        return [v.player_id for v in self.villagers.values() if v.is_alive]

    def reset_all(self):
        """重置所有平民"""
        for villager in self.villagers.values():
            villager.reset_for_new_game()

    def get_all_states(self) -> Dict[int, Dict]:
        """获取所有平民状态"""
        return {pid: villager.get_state_dict() for pid, villager in self.villagers.items()}


# ============ 示例使用 ============

if __name__ == "__main__":
    # 创建平民角色
    villager = Villager(
        player_id=5,
        player_name="村民小明",
        is_villager=True
    )

    print(f"平民创建: {villager}")
    print(f"平民状态: {villager.get_state_dict()}")

    # 模拟接收发言
    print("\n=== 模拟对局 ===")

    # 观察其他玩家发言
    villager.observe_speech(1, "我是预言家，昨晚查了3号，是好人。", 1)
    villager.observe_speech(2, "我是平民，过。", 1)
    villager.observe_speech(3, "我是好人，我觉得1号不像预言家。", 1)

    print(f"\n信任度: {villager.trust_scores}")
    print(f"自称预言家: {villager.self_claimed_predictors}")
    print(f"怀疑对象: {[(pid, r.suspicion_score) for pid, r in villager.suspects.items()]}")

    # 生成发言
    print(f"\n平民发言: {villager.generate_speech(1, 'middle', [1, 2, 3, 4, 5])}")

    # 决定投票
    vote_target = villager.decide_vote_target([1, 2, 3, 4, 5], 1)
    print(f"\n投票目标: {vote_target}号")

    # 记录投票
    villager.record_vote(1, vote_target)

    # 更新状态
    print(f"\n最终状态: {villager.get_state_dict()}")