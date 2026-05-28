import pytest

from app.services.agent_manager import AgentManager
from app.services.game_engine import GameEngine
from app.services.role_system import Team, get_default_composition


class TestGameEngineInit:
    """游戏引擎初始化测试。"""

    def test_engine_creation(self):
        am = AgentManager("test_game")
        engine = GameEngine("test_game", am)
        assert engine.game_id == "test_game"
        assert engine.round == 1
        assert engine.winner is None

    def test_engine_initial_state(self):
        am = AgentManager("test_game")
        engine = GameEngine("test_game", am)
        assert engine.state == {}
        assert engine.logs == []


class TestAgentManagerWithEngine:
    """AgentManager 在游戏引擎中的集成测试。"""

    def test_create_agents_from_composition(self):
        comp = get_default_composition(6)
        player_roles = {}
        for role, count in comp.items():
            for i in range(count):
                player_roles[f"player_{role}_{i}"] = role

        am = AgentManager("test")
        contexts = am.create_agents(player_roles)
        assert len(contexts) == 6

    def test_get_agents_by_team(self):
        player_roles = {
            "p1": "werewolf",
            "p2": "werewolf",
            "p3": "villager",
            "p4": "villager",
            "p5": "seer",
            "p6": "villager",
        }
        am = AgentManager("test")
        am.create_agents(player_roles)

        wolves = am.get_agents_by_team(Team.WEREWOLF)
        villagers = am.get_agents_by_team(Team.VILLAGER)
        assert len(wolves) == 2
        assert len(villagers) == 4

    def test_mark_dead(self):
        player_roles = {"p1": "villager"}
        am = AgentManager("test")
        am.create_agents(player_roles)
        am.mark_dead("p1")
        ctx = am.get_agent("p1")
        assert ctx is not None

    def test_build_visible_info(self):
        player_roles = {"p1": "werewolf", "p2": "werewolf", "p3": "villager"}
        am = AgentManager("test")
        am.create_agents(player_roles)

        game_state = {
            "round": 1,
            "phase": "night",
            "alive_players": [{"id": "p1"}, {"id": "p2"}, {"id": "p3"}],
            "dead_players": [],
            "public_logs": [],
            "werewolf_discussion": [],
            "seer_checks": {},
        }

        visible = am.build_visible_info("p1", game_state)
        assert visible["role_name"] == "werewolf"
        assert "teammates" in visible["extra"]
        assert "p2" in visible["extra"]["teammates"]


class TestWinCondition:
    """胜负判定逻辑测试。"""

    def test_villagers_win_no_werewolves(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        engine.state["alive_players"] = [
            {"id": "p1", "team": "villager"},
            {"id": "p2", "team": "villager"},
        ]
        assert engine._check_win() is True
        assert engine.winner == "villager"

    def test_werewolves_win_majority(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        engine.state["alive_players"] = [
            {"id": "p1", "team": "werewolf"},
            {"id": "p2", "team": "werewolf"},
            {"id": "p3", "team": "villager"},
            {"id": "p4", "team": "villager"},
        ]
        assert engine._check_win() is True
        assert engine.winner == "werewolf"

    def test_game_continues(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        engine.state["alive_players"] = [
            {"id": "p1", "team": "werewolf"},
            {"id": "p2", "team": "villager"},
            {"id": "p3", "team": "villager"},
            {"id": "p4", "team": "villager"},
        ]
        assert engine._check_win() is False
        assert engine.winner is None


class TestLLMResponseParsing:
    """LLM 响应解析测试。"""

    def test_parse_json_direct(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        result = engine._parse_json('{"type": "kill", "target_id": "p1"}')
        assert result == {"type": "kill", "target_id": "p1"}

    def test_parse_json_in_code_block(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        text = '''我决定击杀 p2
```json
{"type": "kill", "target_id": "p2"}
```'''
        result = engine._parse_json(text)
        assert result == {"type": "kill", "target_id": "p2"}

    def test_parse_json_braces(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        text = '我的选择是 {"type": "vote", "target_id": "p3"}'
        result = engine._parse_json(text)
        assert result == {"type": "vote", "target_id": "p3"}

    def test_parse_invalid(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        result = engine._parse_json("not json at all")
        assert result is None

    def test_parse_json_code_block_no_lang(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        text = '''```
{"type": "skip"}
```'''
        result = engine._parse_json(text)
        assert result == {"type": "skip"}

    def test_parse_empty_string(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        assert engine._parse_json("") is None


class TestGameEngineControl:
    """游戏引擎控制（暂停/恢复/停止/单步）测试。"""

    def test_pause_sets_event(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        assert engine.is_paused is False
        engine.pause()
        assert engine.is_paused is True

    def test_resume_clears_pause(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        engine.pause()
        engine.resume()
        assert engine.is_paused is False
        assert engine.is_running is True

    def test_stop_sets_flag(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        assert engine._stopped is False
        engine.stop()
        assert engine._stopped is True
        # stop 也会解除 pause
        assert engine.is_paused is False

    def test_step_sets_mode(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        engine.pause()
        assert engine.is_paused is True
        engine.step()
        # step 解除暂停并设置步进模式
        assert engine.is_paused is False
        assert engine._step_mode is True

    def test_is_running_initial(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        # 初始：未停止，未暂停 → running
        assert engine.is_running is True

    def test_is_running_when_paused(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        engine.pause()
        assert engine.is_running is False

    def test_is_running_when_stopped(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        engine.stop()
        assert engine.is_running is False


class TestGameEngineState:
    """游戏引擎状态查询测试。"""

    def test_get_public_state_structure(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        engine.state = {
            "alive_players": [{"id": "p1", "team": "werewolf"}],
            "dead_players": [],
            "public_logs": [],
            "phase_details": {},
        }
        state = engine.get_public_state()
        assert state["game_id"] == "test"
        assert "round" in state
        assert "phase" in state
        assert "is_paused" in state
        assert "is_running" in state
        assert "winner" in state
        assert "alive_players" in state
        assert "dead_players" in state

    def test_get_result_structure(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        engine.winner = "villager"
        engine.state = {
            "alive_players": [{"id": "p1", "team": "villager"}],
            "dead_players": [{"player_id": "p2", "cause": "vote"}],
        }
        engine.logs = [
            {"timestamp": "2024-01-01T00:00:00", "event": "game_start", "message": "开始"},
        ]
        result = engine.get_result()
        assert result["game_id"] == "test"
        assert result["winner"] == "villager"
        assert "players" in result
        assert "logs" in result
        assert result["logs"][0]["event"] == "game_start"

    def test_extract_action(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        decision = {"action": {"type": "kill", "target_id": "p3"}}
        act = engine._extract_action(decision)
        assert act["type"] == "kill"

    def test_extract_action_no_action_key(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        decision = {"type": "vote", "target_id": "p5"}
        act = engine._extract_action(decision)
        assert act["type"] == "vote"

    def test_load_prompt_werewolf(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        prompt = engine._load_prompt("werewolf")
        assert "狼人" in prompt
        assert "击杀" in prompt

    def test_load_prompt_seer(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        prompt = engine._load_prompt("seer")
        assert "预言家" in prompt

    def test_load_prompt_witch(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        prompt = engine._load_prompt("witch")
        assert "女巫" in prompt

    def test_load_prompt_hunter(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        prompt = engine._load_prompt("hunter")
        assert "猎人" in prompt

    def test_load_prompt_villager(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        prompt = engine._load_prompt("villager")
        assert "村民" in prompt

    def test_load_prompt_nonexistent_returns_empty(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        prompt = engine._load_prompt("nonexistent_role")
        assert prompt == ""


class TestGameEngineBuildContext:
    """_build_context 方法测试（含经验注入）。"""

    def test_build_context_basic(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        visible = {
            "player_id": "p1",
            "role_name": "werewolf",
            "team": "werewolf",
            "round": 2,
            "phase": "night",
            "alive_players": [{"id": "p1"}, {"id": "p2"}],
            "dead_players": [],
            "public_logs": [],
            "extra": {"teammates": ["p2"]},
        }
        ctx = engine._build_context("base prompt", visible, "kill")
        assert "base prompt" in ctx
        assert "第 2 轮" in ctx
        assert "werewolf" in ctx
        assert "kill" in ctx
        assert "teammates" in ctx

    def test_build_context_with_extra_info(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        visible = {
            "player_id": "p1",
            "role_name": "witch",
            "team": "villager",
            "round": 1,
            "phase": "night",
            "alive_players": [],
            "dead_players": [],
            "public_logs": [],
            "extra": {},
        }
        ctx = engine._build_context("prompt", visible, "save", extra_info="击杀目标是 p3")
        assert "击杀目标是 p3" in ctx

    def test_build_context_with_public_logs(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        visible = {
            "player_id": "p1",
            "role_name": "villager",
            "team": "villager",
            "round": 3,
            "phase": "day",
            "alive_players": [],
            "dead_players": [],
            "public_logs": [
                {"round": 2, "speaker": "p2", "content": "我觉得p3很可疑"},
            ],
            "extra": {},
        }
        ctx = engine._build_context("prompt", visible, "vote")
        assert "我觉得p3很可疑" in ctx

    def test_build_context_no_extra(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        visible = {
            "player_id": "p1",
            "role_name": "hunter",
            "team": "villager",
            "round": 1,
            "phase": "day",
            "alive_players": [],
            "dead_players": [],
            "public_logs": [],
            "extra": {},
        }
        ctx = engine._build_context("prompt", visible, "vote")
        assert "你的专属信息" not in ctx  # extra 为空时不显示该段


class TestGameEngineWinConditionEdgeCases:
    """胜负判定边界情况测试。"""

    def test_exact_equal(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        engine.state["alive_players"] = [
            {"id": "p1", "team": "werewolf"},
            {"id": "p2", "team": "werewolf"},
            {"id": "p3", "team": "villager"},
            {"id": "p4", "team": "villager"},
        ]
        assert engine._check_win() is True
        assert engine.winner == "werewolf"

    def test_werewolves_one_more(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        engine.state["alive_players"] = [
            {"id": "p1", "team": "werewolf"},
            {"id": "p2", "team": "werewolf"},
            {"id": "p3", "team": "villager"},
        ]
        assert engine._check_win() is True
        assert engine.winner == "werewolf"

    def test_single_player_left(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        engine.state["alive_players"] = [
            {"id": "p1", "team": "villager"},
        ]
        assert engine._check_win() is True
        assert engine.winner == "villager"

    def test_only_werewolves_left(self):
        am = AgentManager("test")
        engine = GameEngine("test", am)
        engine.state["alive_players"] = [
            {"id": "p1", "team": "werewolf"},
            {"id": "p2", "team": "werewolf"},
        ]
        assert engine._check_win() is True
        assert engine.winner == "werewolf"
