"""FastAPI 接口测试 — 使用 TestClient 测试所有 API 端点。"""

import json
import time

import pytest
from fastapi.testclient import TestClient


def _json(resp):
    """提取响应 JSON，失败时给出可读的错误信息。"""
    assert resp.status_code < 500, f"服务端错误 {resp.status_code}: {resp.text[:300]}"
    return resp.json()


# ==================== 基础端点 ====================

class TestHealth:
    def test_root(self, client: TestClient):
        resp = client.get("/")
        data = _json(resp)
        assert data["status"] == "running"
        assert "version" in data

    def test_health(self, client: TestClient):
        resp = client.get("/health")
        data = _json(resp)
        assert data["status"] == "ok"


# ==================== 创建游戏 ====================

class TestCreateGame:
    def test_create_default(self, client: TestClient):
        resp = client.post("/api/game", json={})
        assert resp.status_code == 201
        data = _json(resp)
        assert data["status"] == "pending"
        assert data["mode"] == "auto"
        assert len(data["players"]) == 9

    def test_create_6_players(self, client: TestClient):
        resp = client.post("/api/game", json={"player_count": 6})
        assert resp.status_code == 201
        data = _json(resp)
        assert len(data["players"]) == 6

    def test_create_12_players(self, client: TestClient):
        resp = client.post("/api/game", json={"player_count": 12})
        assert resp.status_code == 201
        data = _json(resp)
        assert len(data["players"]) == 12

    def test_create_manual_mode(self, client: TestClient):
        resp = client.post("/api/game", json={"mode": "manual"})
        assert resp.status_code == 201
        data = _json(resp)
        assert data["mode"] == "manual"

    def test_create_invalid_player_count(self, client: TestClient):
        resp = client.post("/api/game", json={"player_count": 7})
        assert resp.status_code == 422

    def test_create_invalid_mode(self, client: TestClient):
        resp = client.post("/api/game", json={"mode": "invalid"})
        assert resp.status_code == 422

    def test_create_response_schema(self, client: TestClient):
        """验证响应结构完整性。"""
        resp = client.post("/api/game", json={"player_count": 9, "human_players": 0, "mode": "auto"})
        data = _json(resp)
        assert "game_id" in data
        assert data["status"] == "pending"
        assert data["mode"] == "auto"
        for p in data["players"]:
            assert "id" in p
            assert "name" in p
            assert "role" in p
            assert "team" in p
            assert p["is_alive"] is True

    def test_create_with_human_players(self, client: TestClient):
        resp = client.post("/api/game", json={"player_count": 9, "human_players": 2})
        data = _json(resp)
        human_names = [p["name"] for p in data["players"] if not p["name"].startswith("AI-")]
        assert len(human_names) == 2

    def test_player_roles_are_shuffled(self, client: TestClient):
        """验证角色被随机分配（两次创建的角色顺序不同）。"""
        roles1 = tuple(p["role"] for p in _json(client.post("/api/game", json={"player_count": 12}))["players"])
        roles2 = tuple(p["role"] for p in _json(client.post("/api/game", json={"player_count": 12}))["players"])
        # 极低概率完全相同
        if roles1 == roles2:
            roles3 = tuple(p["role"] for p in _json(client.post("/api/game", json={"player_count": 12}))["players"])
            assert roles1 != roles3, "三次创建角色顺序居然全部相同"


# ==================== 启动游戏 ====================

class TestStartGame:
    @pytest.fixture
    def game_id(self, client: TestClient):
        return _json(client.post("/api/game", json={}))["game_id"]

    def test_start_success(self, client: TestClient, game_id):
        resp = client.post(f"/api/game/{game_id}/start", json={"mode": "auto"})
        data = _json(resp)
        assert data["action"] == "start"
        assert data["status"] == "playing"
        assert data["mode"] == "auto"

    def test_start_manual_mode(self, client: TestClient, game_id):
        resp = client.post(f"/api/game/{game_id}/start", json={"mode": "manual"})
        data = _json(resp)
        assert data["mode"] == "manual"

    def test_start_nonexistent_game(self, client: TestClient):
        resp = client.post("/api/game/nonexistent/start", json={"mode": "auto"})
        assert resp.status_code == 404

    def test_start_already_started(self, client: TestClient, game_id):
        client.post(f"/api/game/{game_id}/start", json={"mode": "auto"})
        resp = client.post(f"/api/game/{game_id}/start", json={"mode": "auto"})
        assert resp.status_code == 400

    def test_start_invalid_mode(self, client: TestClient, game_id):
        resp = client.post(f"/api/game/{game_id}/start", json={"mode": "bad"})
        assert resp.status_code == 422

    def test_start_default_mode(self, client: TestClient, game_id):
        """不传 mode 时默认 auto。"""
        resp = client.post(f"/api/game/{game_id}/start", json={})
        data = _json(resp)
        assert data["mode"] == "auto"


# ==================== 游戏状态查询 ====================

class TestGameState:
    @pytest.fixture
    def game_id(self, client: TestClient):
        return _json(client.post("/api/game", json={}))["game_id"]

    def test_state_pending(self, client: TestClient, game_id):
        resp = client.get(f"/api/game/{game_id}/state")
        data = _json(resp)
        assert data["status"] == "pending"
        assert data["round"] == 0
        assert data["phase"] == ""

    def test_state_after_start(self, client: TestClient, game_id):
        client.post(f"/api/game/{game_id}/start", json={"mode": "auto"})
        resp = client.get(f"/api/game/{game_id}/state")
        data = _json(resp)
        assert data["status"] == "playing"

    def test_state_schema(self, client: TestClient, game_id):
        """验证状态响应结构。"""
        client.post(f"/api/game/{game_id}/start", json={"mode": "auto"})
        data = _json(client.get(f"/api/game/{game_id}/state"))
        assert "game_id" in data
        assert "status" in data
        assert "round" in data
        assert "phase" in data
        assert "mode" in data
        assert "is_paused" in data
        assert "is_running" in data
        assert "winner" in data
        assert "alive_players" in data
        assert "dead_players" in data
        assert "phase_details" in data

    def test_state_nonexistent(self, client: TestClient):
        resp = client.get("/api/game/nonexistent/state")
        assert resp.status_code == 404


# ==================== 控制操作 ====================

class TestGameControl:
    @pytest.fixture
    def game_id(self, client: TestClient):
        gid = _json(client.post("/api/game", json={}))["game_id"]
        client.post(f"/api/game/{gid}/start", json={"mode": "auto"})
        return gid

    def test_pause(self, client: TestClient, game_id):
        resp = client.post(f"/api/game/{game_id}/pause")
        data = _json(resp)
        assert data["action"] == "pause"
        assert data["status"] == "paused"

    def test_resume(self, client: TestClient, game_id):
        client.post(f"/api/game/{game_id}/pause")
        resp = client.post(f"/api/game/{game_id}/resume")
        data = _json(resp)
        assert data["action"] == "resume"
        assert data["status"] == "running"

    def test_stop(self, client: TestClient, game_id):
        resp = client.post(f"/api/game/{game_id}/stop")
        data = _json(resp)
        assert data["action"] == "stop"

    def test_step(self, client: TestClient, game_id):
        # 先暂停再单步
        client.post(f"/api/game/{game_id}/pause")
        resp = client.post(f"/api/game/{game_id}/step")
        data = _json(resp)
        assert data["action"] == "step"

    def test_set_mode_manual(self, client: TestClient, game_id):
        resp = client.post(f"/api/game/{game_id}/mode?mode=manual")
        data = _json(resp)
        assert data["mode"] == "manual"
        assert "手动" in data["message"]

    def test_set_mode_auto(self, client: TestClient, game_id):
        client.post(f"/api/game/{game_id}/mode?mode=manual")
        resp = client.post(f"/api/game/{game_id}/mode?mode=auto")
        data = _json(resp)
        assert data["mode"] == "auto"

    def test_set_mode_invalid(self, client: TestClient, game_id):
        resp = client.post(f"/api/game/{game_id}/mode?mode=bad")
        assert resp.status_code == 422

    def test_control_nonexistent_game(self, client: TestClient):
        for action in ["pause", "resume", "stop", "step"]:
            resp = client.post(f"/api/game/nonexistent/{action}")
            assert resp.status_code == 404, f"{action} 应返回 404"

    def test_control_response_schema(self, client: TestClient, game_id):
        """验证控制操作响应结构。"""
        data = _json(client.post(f"/api/game/{game_id}/pause"))
        assert "game_id" in data
        assert "action" in data
        assert "status" in data
        assert "mode" in data
        assert "message" in data


# ==================== 游戏结果 & 复盘 ====================

class TestGameResult:
    @pytest.fixture
    def game_id(self, client: TestClient):
        return _json(client.post("/api/game", json={}))["game_id"]

    def test_result_pending(self, client: TestClient, game_id):
        resp = client.get(f"/api/game/{game_id}/result")
        data = _json(resp)
        assert data["game_id"] == game_id
        assert data["total_rounds"] == 0

    def test_result_nonexistent(self, client: TestClient):
        resp = client.get("/api/game/nonexistent/result")
        assert resp.status_code == 404

    def test_result_schema(self, client: TestClient, game_id):
        data = _json(client.get(f"/api/game/{game_id}/result"))
        assert "game_id" in data
        assert "winner" in data
        assert "total_rounds" in data
        assert "players" in data
        assert "logs" in data


class TestGameReplay:
    @pytest.fixture
    def game_id(self, client: TestClient):
        return _json(client.post("/api/game", json={}))["game_id"]

    def test_replay_pending(self, client: TestClient, game_id):
        resp = client.get(f"/api/game/{game_id}/replay")
        data = _json(resp)
        assert data["game_id"] == game_id
        assert "players" in data
        assert "rounds" in data

    def test_replay_nonexistent(self, client: TestClient):
        resp = client.get("/api/game/nonexistent/replay")
        assert resp.status_code == 404

    def test_replay_schema(self, client: TestClient, game_id):
        data = _json(client.get(f"/api/game/{game_id}/replay"))
        assert "game_id" in data
        assert "winner" in data
        assert "total_rounds" in data
        assert "players" in data
        assert "rounds" in data
        assert "summaries" in data


# ==================== 游戏列表 & 统计 ====================

class TestGameList:
    def test_list_empty(self, client: TestClient):
        data = _json(client.get("/api/game/list"))
        assert "games" in data
        assert "total" in data

    def test_list_with_games(self, client: TestClient):
        for _ in range(3):
            client.post("/api/game", json={})
        data = _json(client.get("/api/game/list"))
        assert len(data["games"]) == 3
        assert data["total"] == 3

    def test_list_respects_limit(self, client: TestClient):
        for _ in range(5):
            client.post("/api/game", json={})
        data = _json(client.get("/api/game/list?limit=2"))
        assert len(data["games"]) == 2

    def test_list_item_schema(self, client: TestClient):
        client.post("/api/game", json={})
        data = _json(client.get("/api/game/list"))
        g = data["games"][0]
        assert "id" in g
        assert "status" in g
        assert "player_count" in g
        assert "created_at" in g
        assert "winner" in g


class TestGameStats:
    def test_stats_empty(self, client: TestClient):
        data = _json(client.get("/api/game/stats"))
        assert data["total_games"] == 0

    def test_stats_with_games(self, client: TestClient):
        client.post("/api/game", json={})
        client.post("/api/game", json={})
        data = _json(client.get("/api/game/stats"))
        assert data["total_games"] == 2
        assert data["pending"] == 2
        assert "win_rate" in data


# ==================== 玩家操作 ====================

class TestPlayerAction:
    @pytest.fixture
    def ids(self, client: TestClient):
        data = _json(client.post("/api/game", json={"player_count": 6, "human_players": 1}))
        gid = data["game_id"]
        human = [p for p in data["players"] if not p["name"].startswith("AI-")][0]
        client.post(f"/api/game/{gid}/start", json={"mode": "auto"})
        return gid, human["id"]

    def test_player_action(self, client: TestClient, ids):
        gid, pid = ids
        resp = client.post(
            f"/api/game/{gid}/player/{pid}/action",
            json={"action_type": "vote", "target_id": "dummy", "reasoning": "测试"},
        )
        assert resp.status_code == 200

    def test_player_speak(self, client: TestClient, ids):
        gid, pid = ids
        resp = client.post(
            f"/api/game/{gid}/player/{pid}/speak",
            json={"content": "我是村民"},
        )
        assert resp.status_code == 200

    def test_action_on_ai_player(self, client: TestClient, ids):
        gid, _ = ids
        # 找一个 AI 玩家
        state = _json(client.get(f"/api/game/{gid}/state"))
        ai_player = [p for p in state["alive_players"] if p["name"].startswith("AI-")][0]
        resp = client.post(
            f"/api/game/{gid}/player/{ai_player['id']}/action",
            json={"action_type": "vote", "target_id": "dummy"},
        )
        assert resp.status_code == 400  # 不能操作 AI


# ==================== 评测 API ====================

class TestEvaluation:
    def test_report_not_finished(self, client: TestClient):
        gid = _json(client.post("/api/game", json={}))["game_id"]
        client.post(f"/api/game/{gid}/start", json={"mode": "auto"})
        # 游戏还在运行，不能评测
        # 由于游戏是后台运行，可能很快结束也可能没有
        # 这里只验证端点存在且可访问（可能返回 400 或 200）
        resp = client.get(f"/api/evaluation/{gid}/report")
        assert resp.status_code in (200, 400, 404)

    def test_leaderboard(self, client: TestClient):
        resp = client.get("/api/evaluation/leaderboard")
        assert resp.status_code == 200
        data = _json(resp)
        assert "leaderboard" in data

    def test_compare_insufficient(self, client: TestClient):
        resp = client.post("/api/evaluation/compare", json={"game_ids": ["only_one"]})
        assert resp.status_code == 400

    def test_stats(self, client: TestClient):
        resp = client.get("/api/evaluation/stats")
        assert resp.status_code == 200
        data = _json(resp)
        assert "total_games" in data


# ==================== SSE 事件流 ====================

class TestSSEStream:
    @pytest.fixture
    def game_id(self, client: TestClient):
        return _json(client.post("/api/game", json={}))["game_id"]

    def test_stream_connects(self, client: TestClient, game_id):
        """SSE 端点可以连接（验证 Content-Type）。"""
        resp = client.get(f"/api/game/{game_id}/stream", headers={"Accept": "text/event-stream"})
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_stream_nonexistent(self, client: TestClient):
        """不存在的游戏也可以订阅（只是收不到事件）。"""
        resp = client.get("/api/game/nonexistent/stream", headers={"Accept": "text/event-stream"})
        assert resp.status_code == 200


# ==================== 完整流程测试 ====================

class TestFullGameFlow:
    def test_create_start_pause_resume_stop(self, client: TestClient):
        """完整控制流程：创建 → 启动 → 暂停 → 恢复 → 停止。"""
        # 创建
        gid = _json(client.post("/api/game", json={"player_count": 9, "mode": "auto"}))["game_id"]

        # 启动
        data = _json(client.post(f"/api/game/{gid}/start", json={"mode": "auto"}))
        assert data["status"] == "playing"

        # 暂停
        data = _json(client.post(f"/api/game/{gid}/pause"))
        assert data["status"] == "paused"

        # 恢复
        data = _json(client.post(f"/api/game/{gid}/resume"))
        assert data["status"] == "running"

        # 停止
        data = _json(client.post(f"/api/game/{gid}/stop"))
        assert data["action"] == "stop"

    def test_manual_mode_step_flow(self, client: TestClient):
        """手动模式流程：创建 → 启动 → 单步推进。"""
        gid = _json(client.post("/api/game", json={"player_count": 9, "mode": "manual"}))["game_id"]
        data = _json(client.post(f"/api/game/{gid}/start", json={"mode": "manual"}))
        assert data["mode"] == "manual"

        # 单步推进
        step = _json(client.post(f"/api/game/{gid}/step"))
        assert step["action"] == "step"

    def test_mode_switch_during_game(self, client: TestClient):
        """运行时切换模式。"""
        gid = _json(client.post("/api/game", json={"player_count": 9, "mode": "auto"}))["game_id"]
        client.post(f"/api/game/{gid}/start", json={"mode": "auto"})

        # 切到手动
        data = _json(client.post(f"/api/game/{gid}/mode?mode=manual"))
        assert data["mode"] == "manual"

        # 切回自动
        data = _json(client.post(f"/api/game/{gid}/mode?mode=auto"))
        assert data["mode"] == "auto"

    def test_state_reflects_control_actions(self, client: TestClient):
        """控制操作后状态查询反映最新状态。"""
        gid = _json(client.post("/api/game", json={"player_count": 9}))["game_id"]
        client.post(f"/api/game/{gid}/start", json={"mode": "auto"})

        state = _json(client.get(f"/api/game/{gid}/state"))
        assert state["status"] == "playing"

        client.post(f"/api/game/{gid}/pause")
        state = _json(client.get(f"/api/game/{gid}/state"))
        assert state["is_paused"] is True


# ==================== 错误处理 ====================

class TestErrorHandling:
    def test_invalid_json(self, client: TestClient):
        resp = client.post("/api/game", content="not json", headers={"Content-Type": "application/json"})
        assert resp.status_code == 422

    def test_method_not_allowed(self, client: TestClient):
        resp = client.delete("/api/game")
        assert resp.status_code == 405

    def test_player_count_below_min(self, client: TestClient):
        resp = client.post("/api/game", json={"player_count": 3})
        assert resp.status_code == 422

    def test_player_count_above_max(self, client: TestClient):
        resp = client.post("/api/game", json={"player_count": 20})
        assert resp.status_code == 422

    def test_human_players_exceed_total(self, client: TestClient):
        resp = client.post("/api/game", json={"player_count": 9, "human_players": 10})
        assert resp.status_code == 422
