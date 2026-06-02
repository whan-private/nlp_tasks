"""SummaryAgent 总结 Agent 测试。"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.summary_agent import ROLE_NAMES, SummaryAgent
from app.services.memory_service import MemoryService


class TestSummaryAgentParseJson:
    """JSON 解析测试（不依赖 LLM）。"""

    @pytest.fixture
    def agent(self, tmp_path):
        svc = MemoryService(base_dir=str(tmp_path / "memory"))
        agent = SummaryAgent(memory_service=svc)
        # 不初始化真实 OpenAI client
        agent.client = None
        return agent

    def test_parse_direct_json(self, agent):
        result = agent._parse_json('{"summary": "test", "lessons": ["a"], "key_moments": []}')
        assert result["summary"] == "test"
        assert result["lessons"] == ["a"]

    def test_parse_json_in_code_block(self, agent):
        text = """以下是总结：
```json
{"summary": "code block test", "lessons": ["l1"], "key_moments": ["m1"]}
```"""
        result = agent._parse_json(text)
        assert result["summary"] == "code block test"

    def test_parse_json_in_code_block_no_lang(self, agent):
        text = """```
{"summary": "no lang", "lessons": [], "key_moments": []}
```"""
        result = agent._parse_json(text)
        assert result["summary"] == "no lang"

    def test_parse_json_plain_braces(self, agent):
        text = '结论: {"summary": "fallback", "lessons": ["x"], "key_moments": ["y"]}'
        result = agent._parse_json(text)
        assert result["summary"] == "fallback"

    def test_parse_invalid(self, agent):
        result = agent._parse_json("not json here")
        assert result is None

    def test_parse_empty_string(self, agent):
        result = agent._parse_json("")
        assert result is None


class TestSummaryAgentPromptBuilding:
    """提示词构建测试。"""

    @pytest.fixture
    def agent(self, tmp_path):
        svc = MemoryService(base_dir=str(tmp_path / "memory"))
        agent = SummaryAgent(memory_service=svc)
        agent.client = None
        return agent

    def _make_logs(self):
        return [
            {"event": "game_start", "message": "游戏开始", "data": {}},
            {"event": "werewolf_kill", "message": "狼人选定了目标", "data": {"target_id": "p6"}},
            {"event": "game_end", "message": "游戏结束", "data": {"winner": "villager", "round": 3}},
        ]

    def _make_players(self):
        return [
            {"id": "p1_wolf", "role": "werewolf", "team": "werewolf"},
            {"id": "p2_wolf", "role": "werewolf", "team": "werewolf"},
            {"id": "p3_seer", "role": "seer", "team": "villager"},
            {"id": "p4_witch", "role": "witch", "team": "villager"},
            {"id": "p5_hunt", "role": "hunter", "team": "villager"},
            {"id": "p6_vill", "role": "villager", "team": "villager"},
        ]

    def test_prompt_contains_role_name(self, agent):
        prompt = agent._build_summary_prompt("狼人", "werewolf", self._make_logs(), self._make_players(), won=True)
        assert "狼人" in prompt
        assert "胜利" in prompt
        assert "经验教训" in prompt

    def test_prompt_contains_defeat(self, agent):
        prompt = agent._build_summary_prompt("预言家", "seer", self._make_logs(), self._make_players(), won=False)
        assert "失败" in prompt

    def test_prompt_contains_player_info(self, agent):
        prompt = agent._build_summary_prompt("女巫", "witch", self._make_logs(), self._make_players(), won=True)
        # prompt should contain truncated player IDs ([:6]) and roles
        assert "p3_see" in prompt  # p3_seer[:6]
        assert "预言家" in prompt
        assert "p4_wit" in prompt  # p4_witch[:6]

    def test_prompt_contains_log_events(self, agent):
        prompt = agent._build_summary_prompt("村民", "villager", self._make_logs(), self._make_players(), won=True)
        assert "游戏开始" in prompt
        assert "狼人选定了目标" in prompt
        assert "游戏结束" in prompt


class TestSummaryAgentWithMockLLM:
    """使用 Mock LLM 的完整流程测试。"""

    @pytest.fixture
    def agent_and_memory(self, tmp_path):
        svc = MemoryService(base_dir=str(tmp_path / "memory"))
        agent = SummaryAgent(memory_service=svc)

        mock_response = {
            "summary": "狼人本局配合默契，成功隐藏身份至第5轮。关键是在白天发言中保持一致的逻辑。",
            "lessons": [
                "狼人团队应提前商量发言策略",
                "不要同时攻击同一个目标以免暴露",
                "利用村民的互相猜疑转移焦点",
            ],
            "key_moments": [
                "第2轮投票放逐了预言家导致信息断层",
                "女巫第3轮误用毒药毒死了猎人",
            ],
        }

        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = json.dumps(mock_response, ensure_ascii=False)
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        agent.client = mock_client
        yield agent, svc, mock_response
        svc._cache.clear()

    def _make_logs(self):
        return [
            {"event": "game_start", "message": "游戏开始", "data": {}},
            {"event": "werewolf_kill", "message": "狼人选定了目标", "data": {"target_id": "p6"}},
            {"event": "seer_check", "message": "预言家查验了p1", "data": {"result": "werewolf"}},
            {"event": "day_start", "message": "天亮了", "data": {"deaths": ["p6"]}},
            {"event": "vote_result", "message": "投票结果", "data": {"votes": {"p2": "p3"}}},
            {"event": "game_end", "message": "游戏结束", "data": {"winner": "werewolf", "round": 5}},
        ]

    def _make_players(self):
        return [
            {"id": "p1_wolf", "role": "werewolf", "team": "werewolf"},
            {"id": "p2_wolf", "role": "werewolf", "team": "werewolf"},
            {"id": "p3_seer", "role": "seer", "team": "villager"},
            {"id": "p4_witch", "role": "witch", "team": "villager"},
            {"id": "p5_hunt", "role": "hunter", "team": "villager"},
            {"id": "p6_vill", "role": "villager", "team": "villager"},
        ]

    def test_summarize_game_returns_all_roles(self, agent_and_memory):
        agent, svc, _ = agent_and_memory
        results = asyncio.run(agent.summarize_game(
            game_id="game_001",
            game_logs=self._make_logs(),
            players=self._make_players(),
            winner="werewolf",
        ))
        roles = {r["role"] for r in results}
        # 每种角色一份总结（去重）
        assert roles == {"werewolf", "seer", "witch", "hunter", "villager"}
        assert len(results) == 5

    def test_summarize_game_saves_to_memory(self, agent_and_memory):
        agent, svc, _ = agent_and_memory
        asyncio.run(agent.summarize_game(
            game_id="game_001",
            game_logs=self._make_logs(),
            players=self._make_players(),
            winner="werewolf",
        ))
        # 验证每种角色都有经验保存
        for role in ["werewolf", "seer", "witch", "hunter", "villager"]:
            exps = svc.load_experiences(role)
            assert len(exps) == 1
            assert exps[0]["game_id"] == "game_001"

    def test_summarize_game_werewolf_won(self, agent_and_memory):
        agent, svc, mock_resp = agent_and_memory
        asyncio.run(agent.summarize_game(
            game_id="game_002",
            game_logs=self._make_logs(),
            players=self._make_players(),
            winner="werewolf",
        ))
        # 狼人阵营的 won=True
        wolf_exps = svc.load_experiences("werewolf")
        assert wolf_exps[0]["won"] is True
        # 村民阵营的 won=False
        vill_exps = svc.load_experiences("villager")
        assert vill_exps[0]["won"] is False

    def test_summarize_game_villager_won(self, agent_and_memory):
        agent, svc, mock_resp = agent_and_memory
        asyncio.run(agent.summarize_game(
            game_id="game_003",
            game_logs=self._make_logs(),
            players=self._make_players(),
            winner="villager",
        ))
        vill_exps = svc.load_experiences("villager")
        assert vill_exps[0]["won"] is True
        wolf_exps = svc.load_experiences("werewolf")
        assert wolf_exps[0]["won"] is False

    def test_summarize_duplicate_roles_deduplicated(self, agent_and_memory):
        """同角色多名玩家只生成一份总结。"""
        agent, svc, _ = agent_and_memory
        players = [
            {"id": "p1", "role": "villager", "team": "villager"},
            {"id": "p2", "role": "villager", "team": "villager"},
            {"id": "p3", "role": "villager", "team": "villager"},
            {"id": "p4", "role": "werewolf", "team": "werewolf"},
        ]
        results = asyncio.run(agent.summarize_game(
            game_id="game_004",
            game_logs=self._make_logs(),
            players=players,
            winner="villager",
        ))
        assert len(results) == 2  # only villager + werewolf

    def test_summarize_result_structure(self, agent_and_memory):
        agent, svc, mock_resp = agent_and_memory
        results = asyncio.run(agent.summarize_game(
            game_id="game_005",
            game_logs=self._make_logs(),
            players=self._make_players(),
            winner="werewolf",
        ))
        for r in results:
            assert "role" in r
            assert "role_cn" in r
            assert "summary" in r
            assert "lessons" in r
            assert "key_moments" in r
            assert "won" in r
            assert isinstance(r["lessons"], list)
            assert isinstance(r["key_moments"], list)
            assert r["role_cn"] == ROLE_NAMES.get(r["role"], r["role"])


class TestSummaryAgentRoleNames:
    """角色名称映射测试。"""

    def test_all_roles_have_names(self):
        for role in ["werewolf", "seer", "witch", "hunter", "villager"]:
            assert role in ROLE_NAMES
            assert isinstance(ROLE_NAMES[role], str)
            assert len(ROLE_NAMES[role]) > 0
