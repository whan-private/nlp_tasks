import json
from datetime import datetime
from pathlib import Path
from werewolf.core.event_bus import Event


class GameLogger:
    def __init__(self, log_dir: str | None = None):
        default = Path(__file__).resolve().parent.parent.parent / "logs"
        self.log_dir = Path(log_dir) if log_dir else default
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.entries: list[dict] = []
        self.game_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]

    def log(self, event: Event):
        entry = {
            "timestamp": event.timestamp,
            "type": event.type.value,
            "data": event.data,
            "is_public": event.is_public(),
            "private_to": event.private_to,
        }
        self.entries.append(entry)

    def log_raw(self, category: str, data: dict):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": category,
            "data": data,
            "is_public": True,
        }
        self.entries.append(entry)

    def save(self, game_result: dict | None = None):
        output = {
            "game_id": self.game_id,
            "started_at": self.entries[0]["timestamp"] if self.entries else "",
            "ended_at": self.entries[-1]["timestamp"] if self.entries else "",
            "game_result": game_result or {},
            "events": self.entries,
        }
        path = self.log_dir / f"game_{self.game_id}.json"
        path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
        return str(path)

    def get_game_summary(self) -> dict:
        return {
            "game_id": self.game_id,
            "total_events": len(self.entries),
            "phases": [e for e in self.entries if e["type"] == "phase_change"],
            "eliminations": [e for e in self.entries if e["type"] == "player_eliminated"],
        }
