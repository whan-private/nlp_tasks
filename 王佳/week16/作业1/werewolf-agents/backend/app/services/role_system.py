from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


# ==================== 枚举定义 ====================

class Team(str, Enum):
    """阵营"""
    WEREWOLF = "werewolf"   # 狼人阵营
    VILLAGER = "villager"   # 村民阵营


class Phase(str, Enum):
    """游戏阶段"""
    NIGHT = "night"   # 夜晚
    DAY = "day"       # 白天


class ActionType(str, Enum):
    """行动类型"""
    KILL = "kill"        # 狼人杀人
    CHECK = "check"      # 预言家查验
    SAVE = "save"        # 女巫救人（解药）
    POISON = "poison"    # 女巫毒人（毒药）
    SHOOT = "shoot"      # 猎人开枪
    VOTE = "vote"        # 投票放逐
    SPEAK = "speak"      # 发言
    SKIP = "skip"        # 跳过行动


# ==================== 角色配置数据类 ====================

@dataclass
class RoleConfig:
    """角色静态配置"""
    name: str                              # 角色名称
    team: Team                             # 所属阵营
    description: str                       # 角色描述
    night_action: Optional[ActionType] = None   # 夜间行动类型（无则为 None）
    night_action_desc: str = ""            # 夜间行动描述
    night_priority: int = 0                # 夜晚行动优先级，数字越小越先执行


# ==================== 基础角色 ====================

class BaseRole:
    """角色基类 — 定义所有角色共有的属性、行为和胜负判定逻辑。"""

    @property
    def config(self) -> RoleConfig:
        """子类必须重写，返回角色静态配置。"""
        raise NotImplementedError

    def __repr__(self):
        return f"<{self.config.name}({self.config.team.value})>"

    # ---- 便捷属性 ----

    @property
    def name(self) -> str:
        """角色名称"""
        return self.config.name

    @property
    def team(self) -> Team:
        """所属阵营"""
        return self.config.team

    @property
    def description(self) -> str:
        """角色描述"""
        return self.config.description

    # ---- 行动能力判定 ----

    def can_act_at_night(self) -> bool:
        """是否有夜间行动能力"""
        return self.config.night_action is not None

    def can_act_at_day(self) -> bool:
        """白天是否可以发言和投票（所有角色均可）"""
        return True

    def need_night_target(self) -> bool:
        """是否需要选择夜间目标（狼人杀、预言家验、女巫毒）"""
        return self.config.night_action in (
            ActionType.KILL, ActionType.CHECK, ActionType.POISON
        )

    # ---- 胜负判定 ----

    def check_win(self, alive_players: list) -> Optional[Team]:
        """根据当前存活玩家判定胜负。
        返回：
            Team.WEREWOLF — 狼人阵营获胜
            Team.VILLAGER — 村民阵营获胜
            None — 游戏继续
        """
        alive_werewolves = sum(1 for p in alive_players if p.team == Team.WEREWOLF)
        alive_villagers = sum(1 for p in alive_players if p.team == Team.VILLAGER)

        # 狼人全部被消灭 → 村民获胜
        if alive_werewolves == 0:
            return Team.VILLAGER
        # 狼人数量 >= 村民数量 → 狼人获胜
        if alive_werewolves >= alive_villagers:
            return Team.WEREWOLF
        return None


# ==================== 具体角色实现 ====================

class Werewolf(BaseRole):
    """狼人 — 每晚击杀一名玩家，白天伪装成村民隐藏身份。
    与狼队友共享夜间击杀讨论信息。

    胜利条件：存活狼人数 >= 存活村民数
    """

    @property
    def config(self) -> RoleConfig:
        return RoleConfig(
            name="werewolf",
            team=Team.WEREWOLF,
            description="狼人：每晚可以击杀一名玩家，白天伪装成村民隐藏身份。",
            night_action=ActionType.KILL,
            night_action_desc="选择今晚要击杀的目标",
            night_priority=10,  # 狼人最先行动
        )

    def check_win(self, alive_players: list) -> Optional[Team]:
        alive_werewolves = sum(1 for p in alive_players if p.team == Team.WEREWOLF)
        alive_villagers = sum(1 for p in alive_players if p.team == Team.VILLAGER)
        if alive_werewolves >= alive_villagers:
            return Team.WEREWOLF
        return None


class Seer(BaseRole):
    """预言家 — 每晚查验一名玩家的真实阵营，获知其是狼人还是村民。

    胜利条件：所有狼人被消灭
    """

    @property
    def config(self) -> RoleConfig:
        return RoleConfig(
            name="seer",
            team=Team.VILLAGER,
            description="预言家：每晚可以查验一名玩家的真实阵营。",
            night_action=ActionType.CHECK,
            night_action_desc="选择今晚要查验的目标",
            night_priority=20,  # 狼人之后，女巫之前
        )


class Witch(BaseRole):
    """女巫 — 拥有一瓶解药和一瓶毒药，各限用一次。
    解药：救活当晚被狼人杀死的玩家（通常是第一晚使用）。
    毒药：毒杀一名玩家（通常用于确认的狼人）。
    首夜可以自救，之后解药无法对自己使用。

    胜利条件：所有狼人被消灭
    """

    def __init__(self):
        self.antidote_used = False   # 解药是否已使用
        self.poison_used = False     # 毒药是否已使用

    @property
    def config(self) -> RoleConfig:
        return RoleConfig(
            name="witch",
            team=Team.VILLAGER,
            description="女巫：拥有一瓶解药和一瓶毒药，各限用一次。",
            night_action=ActionType.SAVE,
            night_action_desc="决定是否使用解药（救人）或毒药（杀人）",
            night_priority=30,  # 狼人和预言家之后行动
        )

    def can_save(self) -> bool:
        """解药是否可用"""
        return not self.antidote_used

    def can_poison(self) -> bool:
        """毒药是否可用"""
        return not self.poison_used

    def use_antidote(self):
        """消耗解药"""
        self.antidote_used = True

    def use_poison(self):
        """消耗毒药"""
        self.poison_used = True


class Hunter(BaseRole):
    """猎人 — 死亡时可以开枪带走一名玩家。
    触发条件：被狼人杀死或被投票放逐时可开枪；被女巫毒杀时不能开枪。

    胜利条件：所有狼人被消灭
    """

    def __init__(self):
        self.can_shoot = True  # 是否可以开枪

    @property
    def config(self) -> RoleConfig:
        return RoleConfig(
            name="hunter",
            team=Team.VILLAGER,
            description="猎人：被投票出局或被狼人杀死时，可以开枪带走一名玩家。",
            # 猎人无夜间主动行动，开枪为被动触发
        )

    def disable_shoot(self):
        """禁止开枪（被女巫毒杀时调用）"""
        self.can_shoot = False


class Villager(BaseRole):
    """村民 — 无特殊能力，通过分析发言逻辑和投票行为推理出狼人。

    胜利条件：所有狼人被消灭
    """

    @property
    def config(self) -> RoleConfig:
        return RoleConfig(
            name="villager",
            team=Team.VILLAGER,
            description="村民：无特殊能力，通过分析发言和投票找出隐藏的狼人。",
            # 村民无夜间行动
        )


# ==================== 角色注册表 ====================

ROLE_REGISTRY: dict[str, type[BaseRole]] = {
    "werewolf": Werewolf,
    "seer": Seer,
    "witch": Witch,
    "hunter": Hunter,
    "villager": Villager,
}


def create_role(role_name: str) -> BaseRole:
    """根据角色名称创建角色实例。"""
    if role_name not in ROLE_REGISTRY:
        raise ValueError(f"未知角色: {role_name}")
    return ROLE_REGISTRY[role_name]()


def get_default_composition(player_count: int) -> dict[str, int]:
    """根据总人数返回默认角色分配。
    支持 6 人局、9 人局、12 人局三种标准配置。
    """
    compositions = {
        6:  {"werewolf": 2, "seer": 1, "witch": 1,             "villager": 2},
        9:  {"werewolf": 3, "seer": 1, "witch": 1, "hunter": 1, "villager": 3},
        12: {"werewolf": 4, "seer": 1, "witch": 1, "hunter": 1, "villager": 5},
    }
    if player_count not in compositions:
        raise ValueError(f"不支持 {player_count} 人的默认配置，支持: 6/9/12")
    return compositions[player_count]


# ==================== 夜晚行动顺序 ====================

def get_night_action_order(roles: list[BaseRole]) -> list[BaseRole]:
    """按夜晚优先级升序排列需要行动的角色。
    执行顺序：狼人(10) → 预言家(20) → 女巫(30)
    """
    acting = [r for r in roles if r.can_act_at_night()]
    return sorted(acting, key=lambda r: r.config.night_priority)
