import json
from pathlib import Path
from collections import defaultdict


def analyze_game(log_path: str) -> dict:
    data = json.loads(Path(log_path).read_text())
    events = data.get("events", [])
    result = data.get("game_result", {})

    eliminations = result.get("eliminated", [])

    night_deaths = [e for e in events if e["type"] == "player_died"]
    vote_results = [e for e in events if e["type"] == "vote_result"]
    vote_casts = [e for e in events if e["type"] == "vote_cast"]
    speeches = [e for e in events if e["type"] == "public_speech" and not e["data"].get("is_last_words")]
    night_actions = [e for e in events if e["type"] == "night_action"]

    total_players = len(result.get("eliminated", []))
    winner = result.get("winner", "")
    rounds = result.get("rounds", 0)

    wolf_eliminated = sum(1 for e in eliminations if e.get("role") == "werewolf")
    village_eliminated = sum(1 for e in eliminations if e.get("role") != "werewolf")

    return {
        "game_id": data.get("game_id", ""),
        "winner": winner,
        "rounds": rounds,
        "total_eliminated": len(eliminations),
        "wolf_eliminated": wolf_eliminated,
        "village_eliminated": village_eliminated,
        "total_speeches": len(speeches),
        "total_votes": len(vote_casts),
        "night_deaths": len(night_deaths),
    }


def scan_all_logs(log_dir: str = "logs") -> list[dict]:
    path = Path(log_dir)
    results = []
    for f in sorted(path.glob("game_*.json")):
        try:
            results.append(analyze_game(str(f)))
        except Exception as e:
            print(f"  Skip {f.name}: {e}")
    return results


def compute_leaderboard(log_dir: str = "logs") -> dict:
    games = scan_all_logs(log_dir)
    total = len(games)
    if total == 0:
        return {"total_games": 0, "message": "No games found"}

    wins = defaultdict(int)
    for g in games:
        wins[g["winner"]] += 1

    avg_rounds = sum(g["rounds"] for g in games) / total if total else 0
    avg_speeches = sum(g["total_speeches"] for g in games) / total if total else 0
    avg_votes = sum(g["total_votes"] for g in games) / total if total else 0

    wolf_elim_total = sum(g["wolf_eliminated"] for g in games)
    village_elim_total = sum(g["village_eliminated"] for g in games)

    return {
        "total_games": total,
        "village_wins": wins.get("village", 0),
        "werewolf_wins": wins.get("werewolf", 0),
        "village_win_rate": round(wins.get("village", 0) / total * 100, 1) if total else 0,
        "werewolf_win_rate": round(wins.get("werewolf", 0) / total * 100, 1) if total else 0,
        "avg_rounds": round(avg_rounds, 1),
        "avg_speeches_per_game": round(avg_speeches, 1),
        "avg_votes_per_game": round(avg_votes, 1),
        "total_wolves_eliminated": wolf_elim_total,
        "total_villagers_eliminated": village_elim_total,
        "games": games,
    }
