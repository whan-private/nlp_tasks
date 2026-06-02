import json
from pathlib import Path


class ReplayAnalyzer:
    def __init__(self, log_path: str):
        self.data = json.loads(Path(log_path).read_text())
        self.events = self.data.get("events", [])
        self.result = self.data.get("game_result", {})

    def timeline(self) -> list[dict]:
        timeline = []
        for e in self.events:
            if not e.get("is_public", True):
                continue
            timeline.append({
                "time": e.get("timestamp", ""),
                "type": e["type"],
                "summary": self._summarize(e),
            })
        return timeline

    def _summarize(self, event: dict) -> str:
        d = event.get("data", {})
        t = event["type"]
        if t == "phase_change":
            return f"Phase → {d.get('phase', '?')}"
        if t == "public_speech":
            return f"{d.get('player_name', '?')}: {d.get('content', '')[:60]}"
        if t == "vote_cast":
            return f"{d.get('voter_name', '?')} voted for {d.get('target_name', '?')}"
        if t == "vote_result":
            return f"{d.get('eliminated_name', '?')} eliminated by vote"
        if t == "player_eliminated":
            return f"{d.get('player_name', '?')} ({d.get('role', '?')}) eliminated"
        if t == "player_died":
            return f"{d.get('player_name', '?')} ({d.get('role', '?')}) died at night"
        if t == "system":
            return d.get("message", "")
        if t == "night_action":
            if d.get("result"):
                return f"Seer checked {d.get('target_name', '?')} → {d['result']}"
            return d.get("message", "Night action")
        if t == "game_over":
            return f"Game over — {d.get('winner', '?')} wins"
        return json.dumps(d, ensure_ascii=False)[:60]

    def turning_points(self) -> list[dict]:
        points = []
        for i, e in enumerate(self.events):
            d = e.get("data", {})
            if e["type"] == "player_eliminated" and d.get("role") == "werewolf":
                points.append({"index": i, "event": e, "significance": "critical",
                               "summary": f"Wolf {d['player_name']} eliminated"})
            elif e["type"] == "player_eliminated" and d.get("role") == "seer":
                points.append({"index": i, "event": e, "significance": "critical",
                               "summary": f"Seer {d['player_name']} eliminated"})
            elif e["type"] == "player_died" and d.get("role") == "seer":
                points.append({"index": i, "event": e, "significance": "critical",
                               "summary": f"Seer {d['player_name']} killed at night"})
            elif e["type"] == "phase_change" and d.get("winner"):
                points.append({"index": i, "event": e, "significance": "game_over",
                               "summary": f"{d['winner']} wins"})
        return points

    def role_performance(self) -> dict:
        roles = {}
        for e in self.events:
            if e["type"] in ("player_eliminated", "player_died"):
                d = e["data"]
                roles[d["player_name"]] = {
                    "role": d.get("role", "?"),
                    "reason": d["reason"],
                }
        return roles
