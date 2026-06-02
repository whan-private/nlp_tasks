"""AgentManager 信息隔离和团队管理全面测试。"""

import pytest

from app.services.agent_manager import AgentContext, AgentManager
from app.services.role_system import Team, create_role


class TestAgentContext:
    def test_creation(self):
        role = create_role("werewolf")
        ctx = AgentContext(player_id="p1", role_name="werewolf", team=Team.WEREWOLF, role=role)
        assert ctx.player_id == "p1"
        assert ctx.role_name == "werewolf"
        assert ctx.team == Team.WEREWOLF
        assert ctx.agent is None

    def test_with_agent(self):
        from app.agents.werewolf_agent import WerewolfAgent

        role = create_role("werewolf")
        agent = WerewolfAgent("p1", role)
        ctx = AgentContext(player_id="p1", role_name="werewolf", team=Team.WEREWOLF, role=role, agent=agent)
        assert ctx.agent is not None
        assert ctx.agent.player_id == "p1"


class TestAgentManagerBasics:
    """AgentManager 基础方法测试。"""

    @pytest.fixture
    def am(self):
        mgr = AgentManager("test_game")
        player_roles = {
            "p1_wolf": "werewolf",
            "p2_wolf": "werewolf",
            "p3_seer": "seer",
            "p4_witch": "witch",
            "p5_hunt": "hunter",
            "p6_vill": "villager",
        }
        mgr.create_agents(player_roles)
        return mgr

    def test_create_agents_count(self, am):
        assert len(am.agents) == 6

    def test_get_agent(self, am):
        ctx = am.get_agent("p1_wolf")
        assert ctx is not None
        assert ctx.role_name == "werewolf"

    def test_get_agent_nonexistent(self, am):
        assert am.get_agent("nonexistent") is None

    def test_get_agents_by_role(self, am):
        wolves = am.get_agents_by_role("werewolf")
        assert len(wolves) == 2
        assert {c.player_id for c in wolves} == {"p1_wolf", "p2_wolf"}

    def test_get_agents_by_role_single(self, am):
        seers = am.get_agents_by_role("seer")
        assert len(seers) == 1
        assert seers[0].player_id == "p3_seer"

    def test_get_agents_by_role_empty(self, am):
        """请求不存在的角色返回空列表。"""
        assert am.get_agents_by_role("alien") == []

    def test_get_agents_by_team_werewolf(self, am):
        wolves = am.get_agents_by_team(Team.WEREWOLF)
        assert len(wolves) == 2

    def test_get_agents_by_team_villager(self, am):
        villagers = am.get_agents_by_team(Team.VILLAGER)
        assert len(villagers) == 4
        names = {c.role_name for c in villagers}
        assert names == {"seer", "witch", "hunter", "villager"}

    def test_get_team_mates(self, am):
        mates = am.get_team_mates("p1_wolf")
        assert mates == ["p2_wolf"]

    def test_get_team_mates_villager(self, am):
        mates = am.get_team_mates("p6_vill")
        assert len(mates) == 3
        assert "p1_wolf" not in mates  # 不同阵营

    def test_get_team_mates_nonexistent(self, am):
        assert am.get_team_mates("nonexistent") == []

    def test_get_werewolf_teammates(self, am):
        teammates = am.get_werewolf_teammates("p1_wolf")
        assert teammates == ["p2_wolf"]

    def test_get_werewolf_teammates_non_wolf(self, am):
        teammates = am.get_werewolf_teammates("p6_vill")
        assert teammates == []

    def test_mark_dead(self, am):
        from app.agents.villager_agent import VillagerAgent

        ctx = am.get_agent("p6_vill")
        ctx.agent = VillagerAgent("p6_vill", ctx.role)
        am.mark_dead("p6_vill")
        assert ctx.agent.is_alive is False


class TestAgentManagerInfoIsolation:
    """全面信息隔离测试 — 验证每种角色只能看到其权限内的信息。"""

    @pytest.fixture
    def am(self):
        mgr = AgentManager("test_game")
        player_roles = {
            "wolf_1": "werewolf",
            "wolf_2": "werewolf",
            "seer_1": "seer",
            "witch_1": "witch",
            "hunt_1": "hunter",
            "vill_1": "villager",
        }
        mgr.create_agents(player_roles)
        return mgr

    @pytest.fixture
    def game_state(self):
        return {
            "round": 3,
            "phase": "night",
            "alive_players": [
                {"id": "wolf_1", "team": "werewolf"},
                {"id": "wolf_2", "team": "werewolf"},
                {"id": "seer_1", "team": "villager"},
                {"id": "witch_1", "team": "villager"},
                {"id": "hunt_1", "team": "villager"},
                {"id": "vill_1", "team": "villager"},
            ],
            "dead_players": [],
            "public_logs": [
                {"round": 2, "speaker": "wolf_1", "content": "我觉得vill_1很可疑"},
            ],
            "werewolf_discussion": [
                {"wolf_id": "wolf_1", "target_id": "seer_1"},
                {"wolf_id": "wolf_2", "target_id": "seer_1"},
            ],
            "seer_checks": {"wolf_1": "werewolf"},
            "night_kill_target": "seer_1",
        }

    # ---- 狼人 ----

    def test_werewolf_sees_teammates(self, am, game_state):
        visible = am.build_visible_info("wolf_1", game_state)
        assert visible["role_name"] == "werewolf"
        assert "teammates" in visible["extra"]
        assert "wolf_2" in visible["extra"]["teammates"]
        assert "wolf_1" not in visible["extra"]["teammates"]  # 不包含自己

    def test_werewolf_sees_night_discussion(self, am, game_state):
        visible = am.build_visible_info("wolf_1", game_state)
        assert "night_discussion" in visible["extra"]
        assert len(visible["extra"]["night_discussion"]) == 2

    def test_werewolf_cannot_see_seer_checks(self, am, game_state):
        visible = am.build_visible_info("wolf_1", game_state)
        assert "check_results" not in visible["extra"]

    def test_werewolf_cannot_see_potion_status(self, am, game_state):
        visible = am.build_visible_info("wolf_1", game_state)
        assert "antidote_available" not in visible["extra"]
        assert "poison_available" not in visible["extra"]

    # ---- 预言家 ----

    def test_seer_sees_check_results(self, am, game_state):
        visible = am.build_visible_info("seer_1", game_state)
        assert visible["role_name"] == "seer"
        assert "check_results" in visible["extra"]
        assert visible["extra"]["check_results"]["wolf_1"] == "werewolf"

    def test_seer_cannot_see_teammates(self, am, game_state):
        visible = am.build_visible_info("seer_1", game_state)
        assert "teammates" not in visible["extra"]
        assert "night_discussion" not in visible["extra"]

    def test_seer_cannot_see_potion_status(self, am, game_state):
        visible = am.build_visible_info("seer_1", game_state)
        assert "antidote_available" not in visible["extra"]

    # ---- 女巫 ----

    def test_witch_sees_potion_status(self, am, game_state):
        visible = am.build_visible_info("witch_1", game_state)
        assert visible["role_name"] == "witch"
        assert visible["extra"]["antidote_available"] is True
        assert visible["extra"]["poison_available"] is True

    def test_witch_sees_night_kill_target(self, am, game_state):
        visible = am.build_visible_info("witch_1", game_state)
        assert visible["extra"]["night_kill_target"] == "seer_1"

    def test_witch_potions_update_after_use(self, am, game_state):
        witch_ctx = am.get_agent("witch_1")
        witch_ctx.role.use_antidote()
        witch_ctx.role.use_poison()
        visible = am.build_visible_info("witch_1", game_state)
        assert visible["extra"]["antidote_available"] is False
        assert visible["extra"]["poison_available"] is False

    def test_witch_cannot_see_check_results(self, am, game_state):
        visible = am.build_visible_info("witch_1", game_state)
        assert "check_results" not in visible["extra"]

    def test_witch_cannot_see_teammates(self, am, game_state):
        visible = am.build_visible_info("witch_1", game_state)
        assert "teammates" not in visible["extra"]

    # ---- 猎人 ----

    def test_hunter_sees_shoot_status(self, am, game_state):
        visible = am.build_visible_info("hunt_1", game_state)
        assert visible["role_name"] == "hunter"
        assert visible["extra"]["can_shoot"] is True

    def test_hunter_shoot_disabled(self, am, game_state):
        hunt_ctx = am.get_agent("hunt_1")
        hunt_ctx.role.disable_shoot()
        visible = am.build_visible_info("hunt_1", game_state)
        assert visible["extra"]["can_shoot"] is False

    def test_hunter_cannot_see_check_results(self, am, game_state):
        visible = am.build_visible_info("hunt_1", game_state)
        assert "check_results" not in visible["extra"]

    def test_hunter_cannot_see_night_discussion(self, am, game_state):
        visible = am.build_visible_info("hunt_1", game_state)
        assert "night_discussion" not in visible["extra"]

    # ---- 村民 ----

    def test_villager_sees_only_public_info(self, am, game_state):
        visible = am.build_visible_info("vill_1", game_state)
        assert visible["role_name"] == "villager"
        assert visible["extra"] == {}
        assert "check_results" not in visible["extra"]
        assert "teammates" not in visible["extra"]
        assert "night_discussion" not in visible["extra"]

    # ---- 通用 ----

    def test_all_roles_see_basic_info(self, am, game_state):
        """所有角色都应该看到基础游戏状态。"""
        for pid in ["wolf_1", "seer_1", "witch_1", "hunt_1", "vill_1"]:
            visible = am.build_visible_info(pid, game_state)
            assert visible["round"] == 3
            assert visible["phase"] == "night"
            assert visible["team"] in ("werewolf", "villager")
            assert len(visible["alive_players"]) == 6

    def test_all_roles_see_public_logs(self, am, game_state):
        for pid in ["wolf_1", "seer_1", "witch_1", "hunt_1", "vill_1"]:
            visible = am.build_visible_info(pid, game_state)
            assert len(visible["public_logs"]) == 1

    def test_nonexistent_player(self, am, game_state):
        visible = am.build_visible_info("nonexistent", game_state)
        assert visible == game_state  # 原样返回完整状态
