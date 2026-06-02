import pytest

from app.services.evaluator import Evaluator, GameMetrics


class TestGameMetrics:
    def test_default_values(self):
        m = GameMetrics(game_id="test")
        assert m.game_id == "test"
        assert m.winner is None
        assert m.total_rounds == 0
        assert m.overall_score == 0.0


class TestEvaluator:
    def setup_method(self):
        self.evaluator = Evaluator()

    def _make_players(self):
        return [
            {"id": "p1", "role": "werewolf", "team": "werewolf"},
            {"id": "p2", "role": "werewolf", "team": "werewolf"},
            {"id": "p3", "role": "seer", "team": "villager"},
            {"id": "p4", "role": "witch", "team": "villager"},
            {"id": "p5", "role": "hunter", "team": "villager"},
            {"id": "p6", "role": "villager", "team": "villager"},
        ]

    def _make_logs(self, winner="villager"):
        return [
            {"event": "game_start", "data": {}},
            {"event": "werewolf_kill", "data": {"target_id": "p6"}},
            {"event": "seer_check", "data": {"target_id": "p1", "result": "werewolf"}},
            {"event": "witch_save", "data": {"target_id": "p6"}},
            {"event": "night_result", "data": {"deaths": [], "saved": "p6"}},
            {"event": "vote_result", "data": {"votes": {"p3": "p1", "p4": "p1", "p5": "p1", "p6": "p1"}}},
            {"event": "player_eliminated", "data": {"player_id": "p1", "cause": "vote"}},
            {"event": "game_end", "data": {"winner": winner, "round": 3}},
        ]

    def test_evaluate_game_basic(self):
        metrics = self.evaluator.evaluate_game(self._make_logs(), self._make_players())
        assert metrics.winner == "villager"
        assert metrics.total_rounds == 3
        assert metrics.werewolf_team_size == 2
        assert metrics.villager_team_size == 4

    def test_evaluate_seer_accuracy(self):
        logs = self._make_logs()
        metrics = self.evaluator.evaluate_game(logs, self._make_players())
        # seer checked p1 and correctly identified as werewolf
        assert metrics.seer_check_accuracy > 0

    def test_evaluate_villager_vote_accuracy(self):
        logs = self._make_logs()
        metrics = self.evaluator.evaluate_game(logs, self._make_players())
        # p3,p4,p5,p6 all voted for p1 (werewolf) - all correct
        assert metrics.villager_vote_accuracy == 1.0

    def test_evaluate_overall_score_range(self):
        metrics = self.evaluator.evaluate_game(self._make_logs(), self._make_players())
        assert 0 <= metrics.overall_score <= 100

    def test_build_leaderboard(self):
        m1 = GameMetrics(game_id="g1", winner="villager", overall_score=85.0, total_rounds=3)
        m2 = GameMetrics(game_id="g2", winner="werewolf", overall_score=50.0, total_rounds=5)
        m3 = GameMetrics(game_id="g3", winner="villager", overall_score=92.0, total_rounds=2)

        leaderboard = self.evaluator.build_leaderboard([m1, m2, m3])
        assert len(leaderboard) == 3
        assert leaderboard[0]["game_id"] == "g3"  # 最高分排第一
        assert leaderboard[0]["rank"] == 1
        assert leaderboard[2]["game_id"] == "g2"  # 最低分排最后

    def test_compare_games(self):
        m1 = GameMetrics(game_id="g1", winner="villager", overall_score=85.0, total_rounds=3)
        m2 = GameMetrics(game_id="g2", winner="werewolf", overall_score=50.0, total_rounds=5)

        result = self.evaluator.compare_games(["g1", "g2"], [m1, m2])
        assert result["games_compared"] == 2
        assert result["avg_rounds"] == 4.0
        assert result["avg_score"] == 67.5

    def test_compare_nonexistent_games(self):
        result = self.evaluator.compare_games(["nonexistent"], [])
        assert "error" in result

    def test_generate_report(self):
        m = GameMetrics(
            game_id="g1",
            winner="villager",
            total_rounds=3,
            seer_check_accuracy=1.0,
            villager_vote_accuracy=0.8,
            witch_poison_correct=True,
            hunter_shot_correct=None,
            overall_score=90.0,
        )
        report = self.evaluator.generate_report(m)
        assert report["game_id"] == "g1"
        assert "metrics" in report
        assert report["overall_score"] == 90.0
        assert "预言家查验准确率" in report["metrics"]

    def test_evaluate_werewolf_win(self):
        logs = self._make_logs(winner="werewolf")
        metrics = self.evaluator.evaluate_game(logs, self._make_players())
        assert metrics.winner == "werewolf"
        # 狼人获胜得分 <= 80（缺少村民获胜的 20 分加分）
        assert metrics.overall_score <= 80
