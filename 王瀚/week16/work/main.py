import sys, os, random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from werewolf.config import DEFAULT_GAME_CONFIG, LLMConfig
from werewolf.core.orchestrator import Orchestrator
from werewolf.llm.client import LLMClient


def run_game(mock: bool = True, seed: int | None = None) -> dict:
    config = DEFAULT_GAME_CONFIG
    player_names = ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank"][:config.total_players]

    if seed is not None:
        random.seed(seed)

    llm_client = None
    if not mock:
        llm_config = LLMConfig(api_key=os.environ.get("DASHSCOPE_API_KEY", "") or "")
        llm_client = LLMClient(llm_config)

    orchestrator = Orchestrator(config, player_names, llm_client=llm_client, use_mock=mock)
    return orchestrator.run()


def batch_run(n: int = 10):
    results = {"village": 0, "werewolf": 0, "games": []}
    for i in range(n):
        result = run_game(mock=True)
        results["games"].append(result)
        if result["winner"] == "village":
            results["village"] += 1
        else:
            results["werewolf"] += 1
        print(f"  Game {i+1}: {result['winner'].upper():8s} "
              f"(R{result['rounds']} D{result['days']}) "
              f"Log: {Path(result['log_path']).name}")
    print(f"\n--- Batch Result ---")
    print(f"Total: {n} games")
    print(f"Village wins: {results['village']} ({results['village']/n*100:.0f}%)")
    print(f"Werewolf wins: {results['werewolf']} ({results['werewolf']/n*100:.0f}%)")
    return results


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "batch":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        batch_run(n)
    else:
        mock = not (os.environ.get("DASHSCOPE_API_KEY") or "").strip()
        mode = "Mock" if mock else "LLM"
        print(f"[Mode] {mode}")
        result = run_game(mock=mock)
        print(f"=== Game Over ===")
        print(f"Winner: {result['winner'].upper()}")
        print(f"Rounds: {result['rounds']}, Days: {result['days']}")
        for e in result['eliminated']:
            print(f"  R{e['round']}D{e['day']} — {e['player_name']} ({e['role']}) [{e['reason']}]")
        print(f"\nLog: {result['log_path']}")
