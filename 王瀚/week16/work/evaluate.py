"""
AI Werewolf Evaluation CLI

Usage:
  python werewolf/evaluate.py batch [N]     Run N mock games and show stats
  python werewolf/evaluate.py analyze       Analyze all existing logs
  python werewolf/evaluate.py replay <id>   Replay a specific game
  python werewolf/evaluate.py leaderboard   Show leaderboard in terminal
"""

import sys, os, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def cmd_batch(args):
    n = int(args[0]) if args else 10
    from werewolf.main import run_game

    print(f"Running {n} mock games...")
    results = []
    for i in range(n):
        r = run_game(mock=True)
        results.append(r)
        sys.stdout.write(f"\r  Game {i+1}/{n} — {r['winner'].upper()} ({r['rounds']}R {r['days']}D)")
        sys.stdout.flush()
    print()

    wins = {"village": 0, "werewolf": 0}
    for r in results:
        wins[r["winner"]] += 1

    print(f"\n=== Batch Results ({n} games) ===")
    print(f"  Village: {wins['village']} ({wins['village']/n*100:.1f}%)")
    print(f"  Werewolf: {wins['werewolf']} ({wins['werewolf']/n*100:.1f}%)")
    print(f"  Avg rounds: {sum(r['rounds'] for r in results)/n:.1f}")
    print(f"  Logs: {LOG_DIR}")


def cmd_analyze(args):
    from werewolf.evaluation.metrics import compute_leaderboard, analyze_game

    lb = compute_leaderboard(str(LOG_DIR))
    print(f"\n=== Leaderboard Analysis ===")
    print(f"  Total games: {lb['total_games']}")
    print(f"  Village wins: {lb['village_wins']} ({lb['village_win_rate']}%)")
    print(f"  Werewolf wins: {lb['werewolf_wins']} ({lb['werewolf_win_rate']}%)")
    print(f"  Avg rounds: {lb['avg_rounds']}")
    print(f"  Avg speeches/game: {lb['avg_speeches_per_game']}")
    print(f"  Total wolves eliminated: {lb['total_wolves_eliminated']}")

    if lb['games']:
        print(f"\n  Recent games:")
        for g in lb['games'][:10]:
            print(f"    {g['game_id']} — {g['winner']:8s} R{g['rounds']} "
                  f"Speeches:{g['total_speeches']} Votes:{g['total_votes']}")


def cmd_replay(args):
    if not args:
        print("Usage: python werewolf/evaluate.py replay <game_id>")
        return
    game_id = args[0]
    from werewolf.evaluation.replay import ReplayAnalyzer

    for f in LOG_DIR.glob(f"*{game_id}*.json"):
        print(f"\n=== Replay: {game_id} ===")
        analyzer = ReplayAnalyzer(str(f))
        timeline = analyzer.timeline()
        for t in timeline:
            print(f"  [{t['type'][:12]:12s}] {t['summary']}")

        print(f"\n  --- Turning Points ---")
        for tp in analyzer.turning_points():
            print(f"  [{tp['significance']:8s}] {tp['summary']}")

        print(f"\n  --- Role Performance ---")
        for name, info in analyzer.role_performance().items():
            print(f"  {name}: {info['role']} — {info['reason']}")
        return
    print(f"Game {game_id} not found in {LOG_DIR}")


def cmd_leaderboard(args):
    cmd_analyze(args)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    cmds = {
        "batch": cmd_batch,
        "analyze": cmd_analyze,
        "replay": cmd_replay,
        "leaderboard": cmd_leaderboard,
    }

    if cmd in cmds:
        cmds[cmd](args)
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
