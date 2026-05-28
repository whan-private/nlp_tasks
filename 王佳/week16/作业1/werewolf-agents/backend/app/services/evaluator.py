from collections import Counter
from dataclasses import dataclass, field


@dataclass
class GameMetrics:
    """单局游戏的评测指标。"""
    game_id: str
    winner: str | None = None
    total_rounds: int = 0

    # 结果指标
    werewolf_team_size: int = 0
    villager_team_size: int = 0

    # 过程指标
    werewolf_kill_success_rate: float = 0.0  # 狼人击杀成功率（不被救）
    seer_check_accuracy: float = 0.0         # 预言家查验狼人的命中率
    witch_save_used_round: int | None = None  # 女巫解药使用轮次
    witch_poison_correct: bool = False        # 女巫毒药是否毒杀了狼人
    hunter_shot_correct: bool | None = None   # 猎人开枪是否带走了狼人

    # 投票指标
    villager_vote_accuracy: float = 0.0       # 村民投票给狼人的正确率
    werewolf_vote_consistency: float = 0.0    # 狼人投票一致性

    # 综合评分 (0-100)
    overall_score: float = 0.0


@dataclass
class AgentStats:
    """单个 Agent 版本的统计数据。"""
    agent_version: str
    model: str
    games_played: int = 0
    wins: int = 0
    win_rate: float = 0.0
    avg_survival_rounds: float = 0.0
    avg_reasoning_score: float = 0.0
    total_kills: int = 0
    correct_votes: int = 0
    total_votes: int = 0


class Evaluator:
    """评测服务 — 多维度评估游戏质量和 Agent 表现。"""

    def evaluate_game(self, game_logs: list[dict], players: list[dict]) -> GameMetrics:
        """对单局游戏进行多维度评测。

        Args:
            game_logs: 游戏的结构化日志
            players: 玩家信息列表

        Returns:
            GameMetrics 评测结果
        """
        metrics = GameMetrics(game_id="unknown")

        # 基础信息
        werewolves = [p for p in players if p.get("team") == "werewolf"]
        villagers = [p for p in players if p.get("team") == "villager"]
        metrics.werewolf_team_size = len(werewolves)
        metrics.villager_team_size = len(villagers)

        # 分析日志
        kill_attempts = 0
        successful_kills = 0
        seer_checks = 0
        seer_correct_checks = 0
        villager_votes = 0
        villager_correct_votes = 0

        for log in game_logs:
            event = log.get("event", "")
            data = log.get("data", {})

            if event == "werewolf_kill":
                kill_attempts += 1
            elif event == "night_result":
                deaths = data.get("deaths", [])
                saved = data.get("saved")
                successful_kills += len(deaths)
                if saved:
                    kill_attempts += 1  # 被救的也算一次击杀尝试

            elif event == "seer_check":
                seer_checks += 1
                result = data.get("result", "")
                if result == "werewolf":
                    seer_correct_checks += 1

            elif event == "vote_result":
                votes = data.get("votes", {})
                for voter, target in votes.items():
                    voter_info = next((p for p in players if p.get("id") == voter), None)
                    target_info = next((p for p in players if p.get("id") == target), None)
                    if voter_info and target_info:
                        if voter_info.get("team") == "villager":
                            villager_votes += 1
                            if target_info.get("team") == "werewolf":
                                villager_correct_votes += 1

            elif event == "witch_poison":
                data = log.get("data", {})
                target_id = data.get("target_id")
                target_info = next((p for p in players if p.get("id") == target_id), None)
                if target_info and target_info.get("team") == "werewolf":
                    metrics.witch_poison_correct = True

            elif event == "hunter_shoot":
                data = log.get("data", {})
                target_id = data.get("target_id")
                target_info = next((p for p in players if p.get("id") == target_id), None)
                if target_info and target_info.get("team") == "werewolf":
                    metrics.hunter_shot_correct = True

            elif event == "game_end":
                metrics.winner = data.get("winner")
                metrics.total_rounds = data.get("round", 0)

        # 计算指标
        if kill_attempts > 0:
            metrics.werewolf_kill_success_rate = successful_kills / kill_attempts
        if seer_checks > 0:
            metrics.seer_check_accuracy = seer_correct_checks / seer_checks
        if villager_votes > 0:
            metrics.villager_vote_accuracy = villager_correct_votes / villager_votes

        # 综合评分 (0-100)
        metrics.overall_score = self._calculate_overall_score(metrics)

        return metrics

    def _calculate_overall_score(self, m: GameMetrics) -> float:
        """根据各项指标计算综合评分。"""
        score = 50.0  # 基础分
        # 村民胜利加分
        if m.winner == "villager":
            score += 20
        # 预言家准确率加分
        score += m.seer_check_accuracy * 15
        # 村民投票准确率加分
        score += m.villager_vote_accuracy * 15
        return min(100, max(0, score))

    def build_leaderboard(self, games_metrics: list[GameMetrics]) -> list[dict]:
        """生成 Agent 排行榜。"""
        # 简化实现：按综合评分排序
        sorted_metrics = sorted(games_metrics, key=lambda m: m.overall_score, reverse=True)
        return [
            {
                "rank": i + 1,
                "game_id": m.game_id,
                "winner": m.winner,
                "rounds": m.total_rounds,
                "score": round(m.overall_score, 1),
            }
            for i, m in enumerate(sorted_metrics[:20])
        ]

    def compare_games(self, game_ids: list[str], all_metrics: list[GameMetrics]) -> dict:
        """多局对比分析。"""
        target_metrics = [m for m in all_metrics if m.game_id in game_ids]
        if not target_metrics:
            return {"error": "没有找到匹配的游戏"}

        avg_rounds = sum(m.total_rounds for m in target_metrics) / len(target_metrics)
        avg_score = sum(m.overall_score for m in target_metrics) / len(target_metrics)

        return {
            "games_compared": len(target_metrics),
            "avg_rounds": round(avg_rounds, 1),
            "avg_score": round(avg_score, 1),
            "details": [
                {
                    "game_id": m.game_id,
                    "winner": m.winner,
                    "rounds": m.total_rounds,
                    "score": round(m.overall_score, 1),
                }
                for m in target_metrics
            ],
        }

    def generate_report(self, metrics: GameMetrics) -> dict:
        """生成单局详细评估报告。"""
        return {
            "game_id": metrics.game_id,
            "winner": metrics.winner,
            "total_rounds": metrics.total_rounds,
            "metrics": {
                "胜负结果": f"{metrics.winner} 获胜",
                "总轮数": metrics.total_rounds,
                "狼人击杀成功率": f"{metrics.werewolf_kill_success_rate:.0%}",
                "预言家查验准确率": f"{metrics.seer_check_accuracy:.0%}",
                "村民投票正确率": f"{metrics.villager_vote_accuracy:.0%}",
                "女巫毒药是否正确": "是" if metrics.witch_poison_correct else "否" if metrics.witch_poison_correct is not None else "未使用",
                "猎人开枪是否正确": "是" if metrics.hunter_shot_correct else "否" if metrics.hunter_shot_correct is not None else "未触发",
            },
            "overall_score": round(metrics.overall_score, 1),
        }
