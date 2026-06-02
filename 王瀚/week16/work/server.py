import sys, os, json
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
sys.path.insert(0, str(Path(__file__).parent.parent))

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
FRONTEND_DIR = Path(__file__).parent / "frontend"


class WerewolfHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def do_GET(self):
        if self.path == "/api/games":
            self._list_games()
        elif self.path.startswith("/api/games/"):
            game_id = self.path.removeprefix("/api/games/").removesuffix(".json")
            self._get_game(game_id)
        elif self.path == "/api/leaderboard":
            self._get_leaderboard()
        else:
            super().do_GET()

    def _list_games(self):
        games = []
        for f in sorted(LOG_DIR.glob("game_*.json"), reverse=True)[:50]:
            try:
                data = json.loads(f.read_text())
                games.append({
                    "id": data["game_id"],
                    "winner": data.get("game_result", {}).get("winner", "?"),
                    "rounds": data.get("game_result", {}).get("rounds", 0),
                    "created": data.get("started_at", ""),
                    "events": len(data.get("events", [])),
                })
            except:
                pass
        self._send_json(games)

    def _get_game(self, game_id):
        for f in LOG_DIR.glob(f"*{game_id}*.json"):
            data = json.loads(f.read_text())
            self._send_json(data)
            return
        self.send_error(404, "Game not found")

    def _get_leaderboard(self):
        try:
            from werewolf.evaluation.metrics import compute_leaderboard
            lb = compute_leaderboard(str(LOG_DIR))
            self._send_json(lb)
        except Exception as e:
            stats = {"village": 0, "werewolf": 0, "total": 0}
            for f in LOG_DIR.glob("game_*.json"):
                try:
                    data = json.loads(f.read_text())
                    w = data.get("game_result", {}).get("winner", "")
                    if w in stats:
                        stats[w] += 1
                    stats["total"] += 1
                except:
                    pass
            if stats["total"] > 0:
                stats["village_pct"] = round(stats["village"] / stats["total"] * 100, 1)
                stats["werewolf_pct"] = round(stats["werewolf"] / stats["total"] * 100, 1)
            self._send_json(stats)

    def _send_json(self, data):
        resp = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8081
    server = HTTPServer(("0.0.0.0", port), WerewolfHandler)
    print(f"Werewolf Spectator server at http://localhost:{port}")
    print(f"Logs from: {LOG_DIR}")
    server.serve_forever()


if __name__ == "__main__":
    main()
