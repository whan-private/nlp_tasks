from dataclasses import dataclass

import pytest

from app.services.role_system import (
    ActionType,
    BaseRole,
    Hunter,
    Phase,
    RoleConfig,
    Seer,
    Team,
    Villager,
    Werewolf,
    Witch,
    create_role,
    get_default_composition,
    get_night_action_order,
)


# ==================== 测试辅助 ====================

@dataclass
class FakePlayer:
    """模拟玩家对象，仅包含测试胜负判定所需的字段。"""
    team: Team


def make_alive(teams: list[Team]) -> list[FakePlayer]:
    """根据阵营列表创建存活玩家列表。"""
    return [FakePlayer(team=t) for t in teams]


# ==================== 枚举测试 ====================

class TestTeam:
    def test_werwolf_value(self):
        assert Team.WEREWOLF == "werewolf"

    def test_villager_value(self):
        assert Team.VILLAGER == "villager"


class TestPhase:
    def test_night_value(self):
        assert Phase.NIGHT == "night"

    def test_day_value(self):
        assert Phase.DAY == "day"


class TestActionType:
    def test_all_actions_exist(self):
        assert ActionType.KILL == "kill"
        assert ActionType.CHECK == "check"
        assert ActionType.SAVE == "save"
        assert ActionType.POISON == "poison"
        assert ActionType.SHOOT == "shoot"
        assert ActionType.VOTE == "vote"
        assert ActionType.SPEAK == "speak"
        assert ActionType.SKIP == "skip"


# ==================== RoleConfig 测试 ====================

class TestRoleConfig:
    def test_default_values(self):
        config = RoleConfig(name="test", team=Team.VILLAGER, description="测试")
        assert config.night_action is None
        assert config.night_action_desc == ""
        assert config.night_priority == 0

    def test_full_config(self):
        config = RoleConfig(
            name="werewolf",
            team=Team.WEREWOLF,
            description="狼人角色",
            night_action=ActionType.KILL,
            night_action_desc="击杀目标",
            night_priority=10,
        )
        assert config.name == "werewolf"
        assert config.team == Team.WEREWOLF
        assert config.night_action == ActionType.KILL
        assert config.night_priority == 10


# ==================== BaseRole 测试 ====================

class TestBaseRole:
    def test_config_not_implemented(self):
        base = BaseRole()
        with pytest.raises(NotImplementedError):
            _ = base.config

    def test_name_delegates_to_config(self):
        role = Villager()
        assert role.name == "villager"

    def test_team_delegates_to_config(self):
        role = Villager()
        assert role.team == Team.VILLAGER

    def test_can_act_at_day_always_true(self):
        role = Villager()
        assert role.can_act_at_day() is True

    def test_repr(self):
        role = Werewolf()
        assert repr(role) == "<werewolf(werewolf)>"


class TestBaseRoleWinCondition:
    """验证 BaseRole.check_win 的通用逻辑（村民阵营的默认判定）。"""

    def test_villagers_win_when_no_werewolves(self):
        role = Villager()
        players = make_alive([Team.VILLAGER, Team.VILLAGER, Team.VILLAGER])
        assert role.check_win(players) == Team.VILLAGER

    def test_werewolves_win_when_equal_count(self):
        """狼人 == 村民数量时应判狼人胜。"""
        role = Villager()
        players = make_alive([Team.WEREWOLF, Team.WEREWOLF, Team.VILLAGER, Team.VILLAGER])
        assert role.check_win(players) == Team.WEREWOLF

    def test_werewolves_win_when_more_than_villagers(self):
        role = Villager()
        players = make_alive([Team.WEREWOLF, Team.WEREWOLF, Team.WEREWOLF, Team.VILLAGER])
        assert role.check_win(players) == Team.WEREWOLF

    def test_game_continues_when_balanced(self):
        """村民还占多数时游戏继续。"""
        role = Villager()
        players = make_alive([Team.WEREWOLF, Team.VILLAGER, Team.VILLAGER, Team.VILLAGER])
        assert role.check_win(players) is None


# ==================== 狼人测试 ====================

class TestWerewolf:
    def test_config(self):
        w = Werewolf()
        assert w.name == "werewolf"
        assert w.team == Team.WEREWOLF
        assert w.config.night_action == ActionType.KILL
        assert w.config.night_priority == 10

    def test_can_act_at_night(self):
        w = Werewolf()
        assert w.can_act_at_night() is True

    def test_need_night_target(self):
        w = Werewolf()
        assert w.need_night_target() is True

    def test_win_condition_equal_count(self):
        """狼人数 == 村民数 → 狼人胜"""
        w = Werewolf()
        players = make_alive([Team.WEREWOLF, Team.WEREWOLF, Team.VILLAGER, Team.VILLAGER])
        assert w.check_win(players) == Team.WEREWOLF

    def test_win_condition_more_werewolves(self):
        """狼人数 > 村民数 → 狼人胜"""
        w = Werewolf()
        players = make_alive([Team.WEREWOLF, Team.WEREWOLF, Team.WEREWOLF, Team.VILLAGER])
        assert w.check_win(players) == Team.WEREWOLF

    def test_no_win_when_fewer_werewolves(self):
        """狼人数 < 村民数 → 游戏继续"""
        w = Werewolf()
        players = make_alive([Team.WEREWOLF, Team.VILLAGER, Team.VILLAGER, Team.VILLAGER])
        assert w.check_win(players) is None

    def test_werewolf_cannot_self_win_on_zero_werewolves(self):
        """Werewolf.check_win 不检查狼人数为 0 的情况（由村民阵营 check_win 处理）。"""
        w = Werewolf()
        players = make_alive([Team.VILLAGER, Team.VILLAGER])
        assert w.check_win(players) is None


# ==================== 预言家测试 ====================

class TestSeer:
    def test_config(self):
        s = Seer()
        assert s.name == "seer"
        assert s.team == Team.VILLAGER
        assert s.config.night_action == ActionType.CHECK
        assert s.config.night_priority == 20

    def test_can_act_at_night(self):
        s = Seer()
        assert s.can_act_at_night() is True

    def test_need_night_target(self):
        s = Seer()
        assert s.need_night_target() is True

    def test_win_when_no_werewolves(self):
        s = Seer()
        players = make_alive([Team.VILLAGER, Team.VILLAGER])
        assert s.check_win(players) == Team.VILLAGER

    def test_game_continues_when_werewolves_alive(self):
        s = Seer()
        players = make_alive([Team.WEREWOLF, Team.VILLAGER, Team.VILLAGER])
        assert s.check_win(players) is None


# ==================== 女巫测试 ====================

class TestWitch:
    def test_config(self):
        w = Witch()
        assert w.name == "witch"
        assert w.team == Team.VILLAGER
        assert w.config.night_action == ActionType.SAVE
        assert w.config.night_priority == 30

    def test_can_act_at_night(self):
        w = Witch()
        assert w.can_act_at_night() is True

    def test_need_night_target_false(self):
        """女巫不需要选择目标（救人/毒人是二选一，由引擎传入被杀者）。"""
        w = Witch()
        assert w.need_night_target() is False

    def test_initial_state_both_potions_available(self):
        w = Witch()
        assert w.can_save() is True
        assert w.can_poison() is True

    def test_use_antidote_consumes_it(self):
        w = Witch()
        w.use_antidote()
        assert w.can_save() is False
        assert w.can_poison() is True  # 毒药未受影响

    def test_use_poison_consumes_it(self):
        w = Witch()
        w.use_poison()
        assert w.can_poison() is False
        assert w.can_save() is True  # 解药未受影响

    def test_both_potions_used(self):
        w = Witch()
        w.use_antidote()
        w.use_poison()
        assert w.can_save() is False
        assert w.can_poison() is False

    def test_win_when_no_werewolves(self):
        w = Witch()
        players = make_alive([Team.VILLAGER, Team.VILLAGER])
        assert w.check_win(players) == Team.VILLAGER


# ==================== 猎人测试 ====================

class TestHunter:
    def test_config(self):
        h = Hunter()
        assert h.name == "hunter"
        assert h.team == Team.VILLAGER
        assert h.config.night_action is None  # 猎人无夜间主动行动

    def test_can_act_at_night(self):
        h = Hunter()
        assert h.can_act_at_night() is False

    def test_can_shoot_by_default(self):
        h = Hunter()
        assert h.can_shoot is True

    def test_disable_shoot(self):
        h = Hunter()
        h.disable_shoot()
        assert h.can_shoot is False

    def test_win_when_no_werewolves(self):
        h = Hunter()
        players = make_alive([Team.VILLAGER, Team.VILLAGER])
        assert h.check_win(players) == Team.VILLAGER


# ==================== 村民测试 ====================

class TestVillager:
    def test_config(self):
        v = Villager()
        assert v.name == "villager"
        assert v.team == Team.VILLAGER
        assert v.config.night_action is None

    def test_can_act_at_night(self):
        v = Villager()
        assert v.can_act_at_night() is False

    def test_need_night_target(self):
        v = Villager()
        assert v.need_night_target() is False

    def test_win_when_no_werewolves(self):
        v = Villager()
        players = make_alive([Team.VILLAGER, Team.VILLAGER])
        assert v.check_win(players) == Team.VILLAGER

    def test_game_continues_with_werewolves(self):
        v = Villager()
        players = make_alive([Team.WEREWOLF, Team.VILLAGER, Team.VILLAGER])
        assert v.check_win(players) is None


# ==================== 工厂方法与注册表测试 ====================

class TestCreateRole:
    def test_create_all_valid_roles(self):
        for name in ["werewolf", "seer", "witch", "hunter", "villager"]:
            role = create_role(name)
            assert role.name == name

    def test_create_invalid_role(self):
        with pytest.raises(ValueError, match="未知角色"):
            create_role("alien")

    def test_each_role_is_correct_type(self):
        assert isinstance(create_role("werewolf"), Werewolf)
        assert isinstance(create_role("seer"), Seer)
        assert isinstance(create_role("witch"), Witch)
        assert isinstance(create_role("hunter"), Hunter)
        assert isinstance(create_role("villager"), Villager)


# ==================== 默认配置测试 ====================

class TestDefaultComposition:
    def test_6_players(self):
        comp = get_default_composition(6)
        assert comp == {"werewolf": 2, "seer": 1, "witch": 1, "villager": 2}
        assert sum(comp.values()) == 6

    def test_9_players(self):
        comp = get_default_composition(9)
        assert comp == {"werewolf": 3, "seer": 1, "witch": 1, "hunter": 1, "villager": 3}
        assert sum(comp.values()) == 9

    def test_12_players(self):
        comp = get_default_composition(12)
        assert comp == {"werewolf": 4, "seer": 1, "witch": 1, "hunter": 1, "villager": 5}
        assert sum(comp.values()) == 12

    def test_unsupported_count(self):
        with pytest.raises(ValueError, match="不支持"):
            get_default_composition(7)


# ==================== 夜晚行动顺序测试 ====================

class TestNightActionOrder:
    def test_correct_order(self):
        roles = [Witch(), Hunter(), Villager(), Seer(), Werewolf()]
        ordered = get_night_action_order(roles)
        names = [r.name for r in ordered]
        # 狼人(10) → 预言家(20) → 女巫(30)，猎人/村民不参与夜间行动
        assert names == ["werewolf", "seer", "witch"]

    def test_excludes_no_night_action_roles(self):
        """无夜间行动能力的角色不出现在列表中。"""
        roles = [Hunter(), Villager()]
        ordered = get_night_action_order(roles)
        assert ordered == []

    def test_empty_list(self):
        assert get_night_action_order([]) == []
