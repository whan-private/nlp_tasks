"""
狼人杀游戏 - 女巫角色模块
包含女巫的所有属性、技能逻辑和状态管理
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PotionType(Enum):
    """药水类型枚举"""
    ANTIDOTE = "antidote"  # 解药
    POISON = "poison"  # 毒药


class PotionStatus(Enum):
    """药水状态"""
    AVAILABLE = "available"  # 可用
    USED = "used"  # 已使用
    NOT_OWNED = "not_owned"  # 未拥有（标准局女巫有两种药水）


class WitchAction(Enum):
    """女巫可执行的行动"""
    SAVE = "save"  # 救人
    KILL = "kill"  # 毒人
    NONE = "none"  # 不行动


@dataclass
class NightActionResult:
    """夜间行动结果"""
    action_type: WitchAction
    target_player_id: Optional[int] = None
    success: bool = True
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class WitchSkillRecord:
    """女巫技能使用记录（用于复盘）"""
    round_num: int
    potion_type: PotionType
    target_id: int
    target_name: str
    result: str
    night_attack_info: Optional[Dict] = None  # 当晚被狼人袭击的信息


class Witch:
    """
    女巫角色类

    属性说明：
    - player_id: 玩家ID
    - player_name: 玩家名称
    - is_alive: 是否存活
    - antidote_available: 解药是否可用
    - poison_available: 毒药是否可用
    - has_antidote: 是否拥有解药（默认True）
    - has_poison: 是否拥有毒药（默认True）
    - can_self_save: 是否可以自救（规则变体，标准局通常不能自救）
    - know_night_attack: 是否知晓当晚被袭击的目标（标准局女巫能知道）
    - antidote_used_round: 解药使用轮次
    - poison_used_round: 毒药使用轮次
    - save_history: 救人历史记录
    - kill_history: 毒人历史记录
    - action_log: 所有行动日志
    """

    def __init__(
            self,
            player_id: int,
            player_name: str,
            has_antidote: bool = True,
            has_poison: bool = True,
            can_self_save: bool = False,
            know_night_attack: bool = True
    ):
        """
        初始化女巫角色

        Args:
            player_id: 玩家ID
            player_name: 玩家名称
            has_antidote: 是否拥有解药
            has_poison: 是否拥有毒药
            can_self_save: 是否可以自救（标准局通常不能）
            know_night_attack: 是否知晓被袭击目标（标准局女巫能知道）
        """
        self.player_id = player_id
        self.player_name = player_name
        self.is_alive = True

        # 药水状态
        self.has_antidote = has_antidote
        self.has_poison = has_poison
        self.antidote_available = has_antidote
        self.poison_available = has_poison

        # 规则配置
        self.can_self_save = can_self_save
        self.know_night_attack = know_night_attack

        # 使用记录
        self.antidote_used_round: Optional[int] = None
        self.poison_used_round: Optional[int] = None

        # 历史记录
        self.save_history: List[WitchSkillRecord] = []
        self.kill_history: List[WitchSkillRecord] = []
        self.action_log: List[NightActionResult] = []

        # 当前回合信息（夜间临时存储）
        self.current_night_attack_target: Optional[int] = None
        self.current_night_attacker_ids: List[int] = []

        logger.info(f"女巫 {player_name}(ID:{player_id}) 初始化完成 - "
                    f"解药:{has_antidote}, 毒药:{has_poison}, 自救:{can_self_save}")

    def receive_night_info(self, attacked_player_id: Optional[int], attacker_ids: List[int]) -> None:
        """
        夜晚开始时接收信息：谁被狼人袭击了

        Args:
            attacked_player_id: 被袭击的玩家ID，None表示平安夜（无人被袭击）
            attacker_ids: 袭击者ID列表（狼人）
        """
        self.current_night_attack_target = attacked_player_id
        self.current_night_attacker_ids = attacker_ids

        if attacked_player_id is not None and self.know_night_attack:
            logger.info(f"女巫 {self.player_name} 收到夜间信息：{attacked_player_id}号玩家被袭击")
        elif attacked_player_id is None:
            logger.info(f"女巫 {self.player_name} 收到夜间信息：平安夜，无人被袭击")

    def can_use_antidote(self, target_player_id: int) -> tuple[bool, str]:
        """
        检查是否可以使用解药

        Args:
            target_player_id: 目标玩家ID

        Returns:
            (是否可用, 原因说明)
        """
        # 检查解药是否存在
        if not self.antidote_available:
            return False, "解药已使用"

        if not self.has_antidote:
            return False, "女巫未持有解药"

        # 检查是否有人被袭击
        if self.current_night_attack_target is None:
            return False, "今晚无人被袭击，无需使用解药"

        # 检查是否自救（根据规则）
        if target_player_id == self.player_id and not self.can_self_save:
            return False, "规则不允许女巫自救"

        # 检查目标是否是被袭击者
        if target_player_id != self.current_night_attack_target:
            return False, f"目标玩家{target_player_id}未被袭击，无法解救"

        return True, "可以使用解药"

    def use_antidote(self, round_num: int) -> NightActionResult:
        """
        使用解药救人

        Args:
            round_num: 当前轮次

        Returns:
            行动结果
        """
        target_id = self.current_night_attack_target

        # 验证
        can_use, reason = self.can_use_antidote(target_id)
        if not can_use:
            return NightActionResult(
                action_type=WitchAction.SAVE,
                target_player_id=target_id,
                success=False,
                message=reason
            )

        # 使用解药
        self.antidote_available = False
        self.antidote_used_round = round_num

        # 记录历史
        record = WitchSkillRecord(
            round_num=round_num,
            potion_type=PotionType.ANTIDOTE,
            target_id=target_id,
            target_name=f"Player_{target_id}",
            result="success",
            night_attack_info={
                "attacker_ids": self.current_night_attacker_ids,
                "was_attacked": True
            }
        )
        self.save_history.append(record)

        result = NightActionResult(
            action_type=WitchAction.SAVE,
            target_player_id=target_id,
            success=True,
            message=f"女巫 {self.player_name} 使用解药救活了 {target_id} 号玩家"
        )
        self.action_log.append(result)

        logger.info(f"女巫 {self.player_name} 在{round_num}轮使用解药救活 {target_id} 号玩家")

        # 清除当前夜间信息（已处理）
        self.current_night_attack_target = None

        return result

    def can_use_poison(self, target_player_id: int) -> tuple[bool, str]:
        """
        检查是否可以使用毒药

        Args:
            target_player_id: 目标玩家ID

        Returns:
            (是否可用, 原因说明)
        """
        # 检查毒药是否存在
        if not self.poison_available:
            return False, "毒药已使用"

        if not self.has_poison:
            return False, "女巫未持有毒药"

        # 不能毒自己（规则通常不允许）
        if target_player_id == self.player_id:
            return False, "女巫不能毒死自己"

        # 检查是否在同一夜晚既救又毒（规则通常不允许）
        # 这个检查在调用方进行

        return True, "可以使用毒药"

    def use_poison(self, target_player_id: int, round_num: int) -> NightActionResult:
        """
        使用毒药杀人

        Args:
            target_player_id: 目标玩家ID
            round_num: 当前轮次

        Returns:
            行动结果
        """
        # 验证
        can_use, reason = self.can_use_poison(target_player_id)
        if not can_use:
            return NightActionResult(
                action_type=WitchAction.KILL,
                target_player_id=target_player_id,
                success=False,
                message=reason
            )

        # 使用毒药
        self.poison_available = False
        self.poison_used_round = round_num

        # 记录历史
        record = WitchSkillRecord(
            round_num=round_num,
            potion_type=PotionType.POISON,
            target_id=target_player_id,
            target_name=f"Player_{target_player_id}",
            result="success"
        )
        self.kill_history.append(record)

        result = NightActionResult(
            action_type=WitchAction.KILL,
            target_player_id=target_player_id,
            success=True,
            message=f"女巫 {self.player_name} 使用毒药毒杀了 {target_player_id} 号玩家"
        )
        self.action_log.append(result)

        logger.info(f"女巫 {self.player_name} 在{round_num}轮使用毒药毒杀 {target_player_id} 号玩家")

        return result

    def skip_night_action(self, round_num: int) -> NightActionResult:
        """
        夜晚不采取任何行动

        Args:
            round_num: 当前轮次

        Returns:
            行动结果
        """
        result = NightActionResult(
            action_type=WitchAction.NONE,
            success=True,
            message=f"女巫 {self.player_name} 在{round_num}轮选择不行动"
        )
        self.action_log.append(result)

        logger.info(f"女巫 {self.player_name} 在{round_num}轮选择不行动")

        # 清除当前夜间信息
        self.current_night_attack_target = None

        return result

    def has_any_potion(self) -> bool:
        """检查是否还有任何药水可用"""
        return self.antidote_available or self.poison_available

    def get_available_actions(self, round_num: int) -> List[WitchAction]:
        """
        获取当前可用的行动列表

        Args:
            round_num: 当前轮次

        Returns:
            可用的行动列表
        """
        available_actions = []

        # 检查是否可以使用解药（有人被袭击且解药可用）
        if self.current_night_attack_target is not None:
            if self.antidote_available and self.has_antidote:
                # 检查自救规则
                if self.current_night_attack_target != self.player_id or self.can_self_save:
                    available_actions.append(WitchAction.SAVE)

        # 毒药总是可以作为选项（具体目标合法性由can_use_poison检查）
        if self.poison_available and self.has_poison:
            available_actions.append(WitchAction.KILL)

        # 总是可以选择不行动
        available_actions.append(WitchAction.NONE)

        return available_actions

    def get_state_dict(self) -> Dict[str, Any]:
        """
        获取女巫当前状态（用于外部查询）

        Returns:
            状态字典
        """
        return {
            "player_id": self.player_id,
            "player_name": self.player_name,
            "is_alive": self.is_alive,
            "antidote_available": self.antidote_available,
            "poison_available": self.poison_available,
            "has_antidote": self.has_antidote,
            "has_poison": self.has_poison,
            "antidote_used_round": self.antidote_used_round,
            "poison_used_round": self.poison_used_round,
            "can_self_save": self.can_self_save,
            "know_night_attack": self.know_night_attack,
            "total_saves": len(self.save_history),
            "total_kills": len(self.kill_history),
            "current_night_attack_target": self.current_night_attack_target
        }

    def reset_for_new_game(self):
        """重置女巫状态（用于新一局游戏）"""
        self.is_alive = True
        self.antidote_available = self.has_antidote
        self.poison_available = self.has_poison
        self.antidote_used_round = None
        self.poison_used_round = None
        self.save_history = []
        self.kill_history = []
        self.action_log = []
        self.current_night_attack_target = None
        self.current_night_attacker_ids = []

        logger.info(f"女巫 {self.player_name}(ID:{self.player_id}) 状态已重置")

    def die(self):
        """女巫死亡"""
        self.is_alive = False
        logger.info(f"女巫 {self.player_name}(ID:{self.player_id}) 已死亡")

    def revive(self):
        """女巫复活（极少情况，如被其他角色技能复活）"""
        self.is_alive = True
        logger.info(f"女巫 {self.player_name}(ID:{self.player_id}) 已复活")

    def __str__(self) -> str:
        return f"Witch({self.player_name}, ID:{self.player_id}, 解药:{'有' if self.antidote_available else '无'}, 毒药:{'有' if self.poison_available else '无'})"


# ============ 女巫管理器（集成到游戏引擎） ============

class WitchManager:
    """
    女巫管理器 - 负责管理所有女巫角色和夜间行动流程
    """

    def __init__(self, game_config: Optional[Dict] = None):
        """
        初始化女巫管理器

        Args:
            game_config: 游戏配置
        """
        self.witches: Dict[int, Witch] = {}  # player_id -> Witch
        self.game_config = game_config or {}
        self.round_num = 0

    def register_witch(self, witch: Witch) -> None:
        """注册女巫角色"""
        self.witches[witch.player_id] = witch
        logger.info(f"女巫 {witch.player_name} 已注册到管理器")

    def get_witch(self, player_id: int) -> Optional[Witch]:
        """根据玩家ID获取女巫对象"""
        return self.witches.get(player_id)

    def get_alive_witch(self) -> Optional[Witch]:
        """获取存活的且未被毒死的女巫（注意：如果女巫被毒死，游戏结束）"""
        for witch in self.witches.values():
            if witch.is_alive:
                return witch
        return None

    def broadcast_night_info(self, attacked_player_id: Optional[int], attacker_ids: List[int]) -> None:
        """
        向所有存活女巫广播夜间信息

        Args:
            attacked_player_id: 被袭击的玩家ID
            attacker_ids: 袭击者ID列表
        """
        for witch in self.witches.values():
            if witch.is_alive:
                witch.receive_night_info(attacked_player_id, attacker_ids)

    def process_witch_action(
            self,
            witch: Witch,
            action: WitchAction,
            target_id: Optional[int],
            round_num: int
    ) -> NightActionResult:
        """
        处理女巫的行动

        Args:
            witch: 女巫对象
            action: 行动类型
            target_id: 目标玩家ID（毒药时需要）
            round_num: 当前轮次

        Returns:
            行动结果
        """
        if action == WitchAction.SAVE:
            return witch.use_antidote(round_num)
        elif action == WitchAction.KILL and target_id is not None:
            return witch.use_poison(target_id, round_num)
        elif action == WitchAction.NONE:
            return witch.skip_night_action(round_num)
        else:
            return NightActionResult(
                action_type=action,
                success=False,
                message=f"无效的行动: {action}"
            )

    def get_all_witch_states(self) -> Dict[int, Dict]:
        """获取所有女巫的状态"""
        return {pid: witch.get_state_dict() for pid, witch in self.witches.items()}

    def reset_all(self):
        """重置所有女巫状态"""
        for witch in self.witches.values():
            witch.reset_for_new_game()


# ============ 示例使用 ============

if __name__ == "__main__":
    # 创建女巫角色
    witch = Witch(
        player_id=1,
        player_name="灵媒者",
        has_antidote=True,
        has_poison=True,
        can_self_save=False,  # 标准局不能自救
        know_night_attack=True
    )

    print(f"女巫创建: {witch}")
    print(f"女巫状态: {witch.get_state_dict()}")

    # 模拟夜间流程
    round_num = 1

    # 模拟狼人袭击了3号玩家
    witch.receive_night_info(attacked_player_id=3, attacker_ids=[2, 4])

    # 查看可用行动
    available = witch.get_available_actions(round_num)
    print(f"\n可用行动: {[a.value for a in available]}")

    # 测试使用解药
    result = witch.use_antidote(round_num)
    print(f"\n使用解药: {result.message}")

    # 查看更新后的状态
    print(f"\n更新后状态: {witch.get_state_dict()}")

    # 创建女巫管理器示例
    manager = WitchManager()
    manager.register_witch(witch)

    print(f"\n所有女巫状态: {manager.get_all_witch_states()}")