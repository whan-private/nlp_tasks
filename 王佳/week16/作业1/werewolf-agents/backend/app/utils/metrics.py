"""评测指标计算工具 — 为 Evaluator 提供可复用的统计函数。"""

from collections import Counter


def calc_win_rate(wins: int, total: int) -> float:
    """计算胜率（百分比）。"""
    return (wins / total * 100) if total > 0 else 0.0


def calc_success_rate(successes: int, attempts: int) -> float:
    """计算成功率（0~1 之间的小数）。"""
    return (successes / attempts) if attempts > 0 else 0.0


def calc_vote_accuracy(votes: dict[str, str], players: list[dict]) -> float:
    """计算投票准确率：投票给狼人的正确率。

    Args:
        votes: {voter_id: target_id}
        players: [{id, team}, ...]

    Returns:
        0~1 之间的准确率
    """
    player_map = {p["id"]: p for p in players}
    correct = 0
    total = 0
    for voter_id, target_id in votes.items():
        voter = player_map.get(voter_id)
        target = player_map.get(target_id)
        if voter and target:
            total += 1
            if target.get("team") == "werewolf":
                correct += 1
    return calc_success_rate(correct, total)


def calc_activity_score(player_id: str, actions: list[dict]) -> float:
    """计算玩家活跃度评分（发言 + 投票次数归一化）。"""
    player_actions = [a for a in actions if a.get("actor_id") == player_id]
    if not player_actions:
        return 0.0
    speak_count = sum(1 for a in player_actions if a.get("action_type") == "speak")
    vote_count = sum(1 for a in player_actions if a.get("action_type") == "vote")
    return min(1.0, (speak_count * 0.6 + vote_count * 0.4) / 5)


def calc_team_coordination(team_ids: list[str], votes: dict[str, str]) -> float:
    """计算团队协作度：同阵营玩家投票目标的一致性。

    Args:
        team_ids: 同阵营玩家 ID 列表
        votes: {voter_id: target_id}

    Returns:
        0~1 之间的协作度，越高表示投票越一致
    """
    team_votes = [votes[pid] for pid in team_ids if pid in votes]
    if len(team_votes) < 2:
        return 0.0
    most_common_count = Counter(team_votes).most_common(1)[0][1]
    return most_common_count / len(team_votes)


def calc_survival_rounds(player_id: str, game_logs: list[dict]) -> int:
    """根据游戏日志计算玩家存活轮数。"""
    death_round = None
    for log in game_logs:
        event = log.get("event", "")
        data = log.get("data", {})
        if event in ("player_death", "player_eliminated") and data.get("player_id") == player_id:
            death_round = log.get("round", 0)
            break
    return death_round if death_round else log.get("round", 0) if game_logs else 0


def normalize_scores(scores: list[float]) -> list[float]:
    """将分数列表归一化到 0~100 区间。"""
    if not scores:
        return scores
    min_s, max_s = min(scores), max(scores)
    if max_s == min_s:
        return [50.0] * len(scores)
    return [(s - min_s) / (max_s - min_s) * 100 for s in scores]
