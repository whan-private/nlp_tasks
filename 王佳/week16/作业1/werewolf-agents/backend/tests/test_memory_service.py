"""MemoryService 经验记忆服务测试。"""

import json
import tempfile
from pathlib import Path

import pytest

from app.services.memory_service import MemoryService


class TestMemoryService:
    """MemoryService 核心功能测试。"""

    @pytest.fixture
    def svc(self, tmp_path):
        """创建临时目录中的 MemoryService 实例。"""
        svc = MemoryService(base_dir=str(tmp_path / "memory"))
        yield svc
        # 清理缓存避免测试间污染
        svc._cache.clear()

    # ---- 保存与加载 ----

    def test_save_and_load_single(self, svc):
        svc.save_experience(
            role="werewolf",
            game_id="game_001",
            summary="本局狼人通过合理伪装获胜。",
            lessons=["第一晚不要杀高玩", "白天发言要跟风"],
            key_moments=["第3轮投票是关键"],
            won=True,
        )
        exps = svc.load_experiences("werewolf")
        assert len(exps) == 1
        assert exps[0]["game_id"] == "game_001"
        assert exps[0]["role"] == "werewolf"
        assert exps[0]["summary"] == "本局狼人通过合理伪装获胜。"
        assert exps[0]["won"] is True

    def test_save_multiple_ordered_by_recent(self, svc):
        for i in range(5):
            svc.save_experience(
                role="villager",
                game_id=f"game_{i:03d}",
                summary=f"总结 {i}",
                lessons=[],
                key_moments=[],
                won=(i % 2 == 0),
            )
        exps = svc.load_experiences("villager")
        assert len(exps) == 5
        # 最新的在前
        assert exps[0]["game_id"] == "game_004"

    def test_load_with_limit(self, svc):
        for i in range(10):
            svc.save_experience(
                role="seer",
                game_id=f"game_{i:03d}",
                summary=f"总结 {i}",
                lessons=[],
                key_moments=[],
                won=True,
            )
        exps = svc.load_experiences("seer", limit=3)
        assert len(exps) == 3
        assert exps[0]["game_id"] == "game_009"

    def test_load_empty_role(self, svc):
        exps = svc.load_experiences("hunter")
        assert exps == []

    # ---- 持久化 ----

    def test_persistence_across_instances(self, tmp_path):
        base = str(tmp_path / "memory")
        svc1 = MemoryService(base_dir=base)
        svc1.save_experience(
            role="witch",
            game_id="game_001",
            summary="持久化测试",
            lessons=[],
            key_moments=[],
            won=True,
        )

        svc2 = MemoryService(base_dir=base)
        exps = svc2.load_experiences("witch")
        assert len(exps) == 1
        assert exps[0]["game_id"] == "game_001"

    def test_file_contains_valid_json(self, svc):
        svc.save_experience(
            role="villager",
            game_id="game_001",
            summary="测试",
            lessons=["lesson1"],
            key_moments=["moment1"],
            won=True,
        )
        path = svc._file("villager")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) == 1
        assert "timestamp" in data[0]

    # ---- format_for_prompt ----

    def test_format_for_prompt_empty(self, svc):
        text = svc.format_for_prompt("werewolf", limit=3)
        assert text == ""

    def test_format_for_prompt_has_content(self, svc):
        svc.save_experience(
            role="werewolf",
            game_id="game_001",
            summary="狼人应该先杀预言家",
            lessons=["优先击杀信息位", "不要集火同一目标"],
            key_moments=["第1轮查验暴露了预言家"],
            won=True,
        )
        text = svc.format_for_prompt("werewolf", limit=3)
        assert "历史经验" in text
        assert "狼人应该先杀预言家" in text
        assert "优先击杀信息位" in text

    def test_format_for_prompt_respects_limit(self, svc):
        for i in range(10):
            svc.save_experience(
                role="seer",
                game_id=f"game_{i:03d}",
                summary=f"总结 {i}",
                lessons=[],
                key_moments=[],
                won=True,
            )
        text = svc.format_for_prompt("seer", limit=2)
        # 应该只有最近 2 条经验
        assert "总结 9" in text
        assert "总结 8" in text
        assert "总结 0" not in text

    def test_format_for_prompt_includes_outcome(self, svc):
        svc.save_experience(
            role="villager",
            game_id="game_001",
            summary="村民方失败，狼人隐藏太好。",
            lessons=[],
            key_moments=[],
            won=False,
        )
        text = svc.format_for_prompt("villager", limit=1)
        assert "失败" in text

    # ---- 统计 ----

    def test_get_stats_empty(self, svc):
        stats = svc.get_stats()
        assert stats["werewolf"]["total"] == 0
        assert stats["seer"]["total"] == 0

    def test_get_stats_with_data(self, svc):
        for i in range(3):
            svc.save_experience(
                role="werewolf",
                game_id=f"game_{i:03d}",
                summary="...",
                lessons=[],
                key_moments=[],
                won=(i < 2),  # 2 wins, 1 loss
            )
        svc.save_experience(
            role="villager",
            game_id="game_010",
            summary="...",
            lessons=[],
            key_moments=[],
            won=True,
        )
        stats = svc.get_stats()
        assert stats["werewolf"]["total"] == 3
        assert stats["werewolf"]["wins"] == 2
        assert stats["villager"]["total"] == 1
        assert stats["villager"]["wins"] == 1

    # ---- 多角色隔离 ----

    def test_roles_are_isolated(self, svc):
        svc.save_experience(
            role="werewolf",
            game_id="game_001",
            summary="狼人经验",
            lessons=[],
            key_moments=[],
            won=True,
        )
        svc.save_experience(
            role="villager",
            game_id="game_001",
            summary="村民经验",
            lessons=[],
            key_moments=[],
            won=False,
        )
        wolf_exps = svc.load_experiences("werewolf")
        vill_exps = svc.load_experiences("villager")
        assert len(wolf_exps) == 1
        assert len(vill_exps) == 1
        assert wolf_exps[0]["summary"] == "狼人经验"
        assert vill_exps[0]["summary"] == "村民经验"
