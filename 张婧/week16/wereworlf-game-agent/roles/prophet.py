"""
狼人杀游戏 - 预言家角色模块
预言家是好人阵营的核心信息位，通过查验技能获取关键信息
"""

from enum import Enum
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CheckResult(Enum):
    """查验结果"""
    WEREWOLF = "werewolf"  # 狼人
    VILLAGER = "villager"  # 村民
    SEER = "seer"  # 预言家
    WITCH = "witch"  # 女巫
    HUNTER = "hunter"  # 猎人
    IDIOT = "idiot"  # 白痴
    UNKNOWN = "unknown"  # 未知


class NightCheckRecord:
    """夜间查验记录"""

    def __init__(self, round_num: int, target_id: int, result: CheckResult):
        self.round_num = round_num
        self.target_id = target_id
        self.result = result
        self.timestamp = datetime.now()

    def to_dict(self) -> Dict:
        return {
            "round": self.round_num,
            "target": self.target_id,
            "result": self.result.value,
            "time": self.timestamp.isoformat()
        }


@dataclass
class SeerMemory:
    """预言家的记忆单元"""
    round_num: int
    event_type: str  # 'check', 'speech', 'vote', 'death', 'claim'
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


class SeerClaimStatus(Enum):
    """跳预言家状态"""
    NOT_CLAIMED = "not_claimed"  # 未起跳
    CLAIMED = "claimed"  # 已起跳
    RETRACTED = "retracted"  # 已退水


class Seer:
    """
    预言家角色类

    预言家是好人阵营的核心，拥有查验身份的能力。
    预言家的核心价值在于：
    1. 夜间查验玩家身份，获取关键信息
    2. 白天起跳报出查验结果，带领好人阵营
    3. 设置警徽流，最大化信息价值
    4. 应对狼人悍跳，争取好人信任

    属性说明：
    - player_id: 玩家ID
    - player_name: 玩家名称
    - is_alive: 是否存活
    - can_check: 是否可以查验（每轮一次）
    - check_history: 查验历史记录
    - claim_status: 跳预言家状态
    - seer_line: 警徽流（预留给警徽的查验顺序）
    - trust_score: 其他玩家对预言家的信任度（从外部感知）
    - exposed_info: 已公开的查验信息
    """

    def __init__(
            self,
            player_id: int,
            player_name: str,
            has_sheriff_badge: bool = False  # 是否持有警徽
    ):
        """
        初始化预言家角色

        Args:
            player_id: 玩家ID
            player_name: 玩家名称
            has_sheriff_badge: 是否持有警徽
        """
        self.player_id = player_id
        self.player_name = player_name
        self.role_type = "seer"
        self.is_alive = True

        # 查验相关
        self.can_check = True  # 每轮可以查验一次
        self.check_history: List[NightCheckRecord] = []
        self.current_check_target: Optional[int] = None
        self.current_check_result: Optional[CheckResult] = None

        # 警徽流 (通常留两个查验目标)
        self.seer_line: List[int] = []  # 警徽流查验顺序
        self.has_sheriff_badge = has_sheriff_badge

        # 身份状态
        self.claim_status = SeerClaimStatus.NOT_CLAIMED
        self.is_trusted: Dict[int, float] = {}  # 各玩家对预言家的信任度

        # 信息管理
        self.exposed_info: Dict[int, CheckResult] = {}  # 已公开的查验结果
        self.known_werewolves: Set[int] = set()  # 已知狼人
        self.known_good_players: Set[int] = set()  # 已知好人

        # 对抗悍跳
        self.opponent_seer: Optional[int] = None  # 悍跳的狼人
        self.opponent_claims: Dict[int, str] = {}  # 对手的发言和查验

        # 记忆系统
        self.memory: List[SeerMemory] = []
        self.speech_history: List[Dict] = []  # 发言历史

        # 策略配置
        self.is_aggressive = True  # 是否激进（积极起跳）
        self.check_strategy = "random"  # 查验策略: 'random', 'suspicious', 'neighbor'

        logger.info(f"预言家 {player_name}(ID:{player_id}) 初始化完成 - 警徽:{has_sheriff_badge}")

    # ============ 查验技能方法 ============

    def can_perform_check(self) -> bool:
        """检查是否可以进行查验"""
        return self.is_alive and self.can_check

    def perform_check(self, target_id: int, target_role: str, round_num: int) -> NightCheckRecord:
        """
        执行查验（由游戏引擎调用，传入真实身份）

        Args:
            target_id: 目标玩家ID
            target_role: 目标玩家的真实角色
            round_num: 当前轮次

        Returns:
            查验记录
        """
        if not self.can_perform_check():
            raise ValueError(f"预言家 {self.player_name} 无法进行查验")

        # 转换为查验结果枚举
        result = self._role_to_check_result(target_role)

        # 创建记录
        record = NightCheckRecord(round_num, target_id, result)
        self.check_history.append(record)

        # 更新状态
        self.current_check_target = target_id
        self.current_check_result = result
        self.can_check = False  # 本回合已使用

        # 更新已知信息
        if result == CheckResult.WEREWOLF:
            self.known_werewolves.add(target_id)
        else:
            self.known_good_players.add(target_id)

        # 记录记忆
        self.memory.append(SeerMemory(
            round_num=round_num,
            event_type="check",
            content=f"查验 {target_id} 号玩家，结果是 {result.value}"
        ))

        logger.info(f"预言家 {self.player_name} 在{round_num}轮查验 {target_id} 号玩家，结果: {result.value}")

        return record

    def _role_to_check_result(self, role: str) -> CheckResult:
        """将角色字符串转换为查验结果枚举"""
        role_mapping = {
            "werewolf": CheckResult.WEREWOLF,
            "villager": CheckResult.VILLAGER,
            "seer": CheckResult.SEER,
            "witch": CheckResult.WITCH,
            "hunter": CheckResult.HUNTER,
            "idiot": CheckResult.IDIOT
        }
        return role_mapping.get(role.lower(), CheckResult.UNKNOWN)

    def reset_night_action(self):
        """重置夜间行动（进入新的一天时调用）"""
        self.can_check = True
        self.current_check_target = None
        self.current_check_result = None

    # ============ 警徽流方法 ============

    def set_seer_line(self, first_target: int, second_target: Optional[int] = None):
        """
        设置警徽流

        警徽流是预言家的重要策略：
        - 如果预言家死亡，可以通过警徽传递来告知查验结果
        - 第一警徽流通常查最可疑的玩家
        - 第二警徽流查次可疑的玩家

        Args:
            first_target: 第一警徽流目标
            second_target: 第二警徽流目标（可选）
        """
        self.seer_line = [first_target]
        if second_target is not None:
            self.seer_line.append(second_target)

        logger.info(f"预言家 {self.player_name} 设置警徽流: {self.seer_line}")

    def get_seer_line_display(self) -> str:
        """获取警徽流展示文本"""
        if not self.seer_line:
            return "未设置警徽流"

        if len(self.seer_line) == 1:
            return f"第一警徽流: {self.seer_line[0]}号"
        else:
            return f"第一警徽流: {self.seer_line[0]}号，第二警徽流: {self.seer_line[1]}号"

    def interpret_sheriff_pass(self, sheriff_receiver: Optional[int]) -> Optional[CheckResult]:
        """
        解释警徽传递的查验结果

        预言家死亡后，如果持有警徽：
        - 将警徽传给好人 → 说明最后查验的是好人
        - 将警徽传给狼人（不存在）→ 通常传给其他好人或撕掉

        Args:
            sheriff_receiver: 获得警徽的玩家ID

        Returns:
            推断的查验结果
        """
        if not self.seer_line:
            return None

        # 如果还有未查验的目标
        if self.seer_line:
            last_target = self.seer_line[-1]
            if sheriff_receiver == last_target:
                return CheckResult.GOOD  # 实际应返回对应的结果
            elif sheriff_receiver is None:
                return CheckResult.WEREWOLF  # 警徽被撕 → 查杀

        return None

    # ============ 信息管理方法 ============

    def reveal_check_result(self, target_id: int, round_num: int):
        """
        公开查验结果（白天发言时）

        Args:
            target_id: 查验目标ID
            round_num: 当前轮次
        """
        # 查找对应的查验记录
        for record in self.check_history:
            if record.target_id == target_id:
                self.exposed_info[target_id] = record.result

                self.memory.append(SeerMemory(
                    round_num=round_num,
                    event_type="reveal",
                    content=f"公开查验结果: {target_id}号是{record.result.value}"
                ))

                logger.info(f"预言家 {self.player_name} 公开查验: {target_id}号是{record.result.value}")
                return

        logger.warning(f"预言家 {self.player_name} 尝试公开未查验的目标: {target_id}")

    def get_check_result_text(self, target_id: int) -> str:
        """获取查验结果的文本描述"""
        # 检查是否已公开
        if target_id in self.exposed_info:
            result = self.exposed_info[target_id]
        else:
            # 从历史中查找
            for record in self.check_history:
                if record.target_id == target_id:
                    result = record.result
                    break
            else:
                return "未查验"

        if result == CheckResult.WEREWOLF:
            return "查杀"
        elif result in [CheckResult.VILLAGER, CheckResult.SEER, CheckResult.WITCH, CheckResult.HUNTER,
                        CheckResult.IDIOT]:
            return "金水"
        else:
            return "未知"

    # ============ 决策方法 ============

    def decide_check_target(
            self,
            alive_players: List[int],
            round_num: int,
            suspicious_players: List[int] = None
    ) -> Optional[int]:
        """
        决定查验目标

        查验策略：
        1. 查验悍跳狼的查杀/金水
        2. 查验划水或行为异常的玩家
        3. 查验之前未查验过的关键位置

        Args:
            alive_players: 存活玩家列表
            round_num: 当前轮次
            suspicious_players: 外部提供的可疑列表

        Returns:
            查验目标ID
        """
        if not self.can_perform_check():
            return None

        # 过滤掉已查验过的玩家
        checked_players = {r.target_id for r in self.check_history}
        candidates = [p for p in alive_players if p not in checked_players and p != self.player_id]

        if not candidates:
            # 如果都查过了，从存活中随机选
            candidates = [p for p in alive_players if p != self.player_id]

        # 根据策略选择目标
        if self.check_strategy == "suspicious" and suspicious_players:
            # 优先查可疑玩家
            for sus in suspicious_players:
                if sus in candidates:
                    return sus

        elif self.check_strategy == "neighbor":
            # 查相邻玩家
            for candidate in candidates:
                if abs(candidate - self.player_id) <= 2:
                    return candidate

        # 默认：随机选择（实际应用中可用更智能的策略）
        import random
        return random.choice(candidates) if candidates else None

    def decide_claim(self, round_num: int) -> bool:
        """
        决定是否起跳预言家

        通常在第一天白天起跳

        Returns:
            是否起跳
        """
        if self.claim_status != SeerClaimStatus.NOT_CLAIMED:
            return False

        # 积极策略：第一轮就起跳
        if self.is_aggressive and round_num == 1:
            return True

        # 被动策略：只有在有查验信息时才起跳
        if self.check_history and round_num <= 2:
            return True

        return False

    def generate_claim_speech(self, round_num: int) -> str:
        """
        生成起跳发言

        Returns:
            完整的起跳发言文本
        """
        if not self.check_history:
            return "我是预言家，今晚会开始查验，请大家相信我。"

        # 获取最近的查验结果
        last_check = self.check_history[-1]
        result_text = self.get_check_result_text(last_check.target_id)

        speech_parts = [
            "我是预言家，",
            f"昨晚查验了{last_check.target_id}号玩家，",
            f"是{result_text}。",
            f"{self.get_seer_line_display()}。",
            "请好人玩家们投给我警徽，我会带领大家找出所有狼人。过。"
        ]

        return "".join(speech_parts)

    def handle_counter_claim(self, opponent_id: int, opponent_speech: str, round_num: int):
        """
        处理悍跳（对手假跳预言家）

        Args:
            opponent_id: 对手玩家ID
            opponent_speech: 对手的发言内容
            round_num: 当前轮次
        """
        self.opponent_seer = opponent_id
        self.opponent_claims[round_num] = opponent_speech

        self.memory.append(SeerMemory(
            round_num=round_num,
            event_type="counter_claim",
            content=f"{opponent_id}号悍跳预言家，发言: {opponent_speech[:50]}..."
        ))

        logger.info(f"预言家 {self.player_name} 遭遇悍跳，对手: {opponent_id}")

    def get_trust_level(self, player_id: int) -> float:
        """获取某玩家对预言家的信任度"""
        return self.is_trusted.get(player_id, 0.5)

    def update_trust(self, player_id: int, delta: float):
        """更新信任度"""
        current = self.is_trusted.get(player_id, 0.5)
        self.is_trusted[player_id] = max(0.0, min(1.0, current + delta))

    # ============ 状态管理方法 ============

    def get_state_dict(self) -> Dict[str, Any]:
        """获取预言家当前状态"""
        return {
            "player_id": self.player_id,
            "player_name": self.player_name,
            "role_type": self.role_type,
            "is_alive": self.is_alive,
            "can_check": self.can_check,
            "check_history": [r.to_dict() for r in self.check_history],
            "seer_line": self.seer_line.copy(),
            "has_sheriff_badge": self.has_sheriff_badge,
            "claim_status": self.claim_status.value,
            "exposed_info": {k: v.value for k, v in self.exposed_info.items()},
            "known_werewolves": list(self.known_werewolves),
            "known_good_players": list(self.known_good_players),
            "opponent_seer": self.opponent_seer,
            "is_aggressive": self.is_aggressive,
            "check_strategy": self.check_strategy
        }

    def reset_for_new_game(self):
        """重置预言家状态（用于新一局游戏）"""
        self.is_alive = True
        self.can_check = True
        self.check_history = []
        self.current_check_target = None
        self.current_check_result = None
        self.seer_line = []
        self.claim_status = SeerClaimStatus.NOT_CLAIMED
        self.is_trusted = {}
        self.exposed_info = {}
        self.known_werewolves = set()
        self.known_good_players = set()
        self.opponent_seer = None
        self.opponent_claims = {}
        self.memory = []
        self.speech_history = []

        logger.info(f"预言家 {self.player_name}(ID:{self.player_id}) 状态已重置")

    def die(self):
        """预言家死亡"""
        self.is_alive = False
        logger.info(f"预言家 {self.player_name}(ID:{self.player_id}) 已死亡")

    def set_sheriff_badge(self, has_badge: bool):
        """设置警徽状态"""
        self.has_sheriff_badge = has_badge

    def __str__(self) -> str:
        check_count = len(self.check_history)
        return f"Seer({self.player_name}, ID:{self.player_id}, 查验次数:{check_count}, 存活:{self.is_alive})"


# ============ 预言家管理器 ============

class SeerManager:
    """
    预言家管理器 - 管理预言家角色和夜间查验流程
    """

    def __init__(self, game_config: Optional[Dict] = None):
        """
        初始化预言家管理器

        Args:
            game_config: 游戏配置
        """
        self.seers: Dict[int, Seer] = {}
        self.game_config = game_config or {}
        self.round_num = 0

    def register_seer(self, seer: Seer) -> None:
        """注册预言家角色"""
        self.seers[seer.player_id] = seer
        logger.info(f"预言家 {seer.player_name} 已注册到管理器")

    def get_seer(self, player_id: int) -> Optional[Seer]:
        """根据玩家ID获取预言家对象"""
        return self.seers.get(player_id)

    def get_alive_seer(self) -> Optional[Seer]:
        """获取存活的预言家"""
        for seer in self.seers.values():
            if seer.is_alive:
                return seer
        return None

    def process_night_check(
            self,
            seer: Seer,
            target_id: int,
            target_role: str,
            round_num: int
    ) -> NightCheckRecord:
        """
        处理夜间查验

        Args:
            seer: 预言家对象
            target_id: 查验目标ID
            target_role: 目标真实角色
            round_num: 当前轮次

        Returns:
            查验记录
        """
        return seer.perform_check(target_id, target_role, round_num)

    def reset_all_night_actions(self):
        """重置所有预言家的夜间行动"""
        for seer in self.seers.values():
            if seer.is_alive:
                seer.reset_night_action()

    def get_all_seer_states(self) -> Dict[int, Dict]:
        """获取所有预言家的状态"""
        return {pid: seer.get_state_dict() for pid, seer in self.seers.items()}

    def reset_all(self):
        """重置所有预言家状态"""
        for seer in self.seers.values():
            seer.reset_for_new_game()


# ============ 示例使用 ============

if __name__ == "__main__":
    # 创建预言家角色
    seer = Seer(
        player_id=1,
        player_name="先知艾琳",
        has_sheriff_badge=False
    )

    print(f"预言家创建: {seer}")
    print(f"预言家状态: {seer.get_state_dict()}")

    # 模拟夜间流程
    print("\n=== 模拟对局 ===")
    round_num = 1

    # 设置警徽流
    seer.set_seer_line(first_target=3, second_target=5)
    print(f"警徽流: {seer.get_seer_line_display()}")

    # 决定查验目标
    target = seer.decide_check_target([1, 2, 3, 4, 5, 6], round_num)
    print(f"决定查验: {target}号玩家")

    # 执行查验（游戏引擎传入真实身份）
    if target:
        record = seer.perform_check(target, "werewolf", round_num)
        print(f"查验结果: {record.result.value}")

    # 决定是否起跳
    should_claim = seer.decide_claim(round_num)
    print(f"是否起跳: {should_claim}")

    if should_claim:
        seer.claim_status = SeerClaimStatus.CLAIMED
        speech = seer.generate_claim_speech(round_num)
        print(f"\n起跳发言: {speech}")

        # 公开查验结果
        seer.reveal_check_result(target, round_num)

    # 处理悍跳
    print("\n=== 处理悍跳 ===")
    seer.handle_counter_claim(opponent_id=6, opponent_speech="我是真预言家，昨晚查了1号是狼人！", round_num=round_num)

    # 最终状态
    print(f"\n最终状态: {seer.get_state_dict()}")

    # 重置夜间行动
    seer.reset_night_action()
    print(f"\n重置后查验状态: can_check={seer.can_check}")