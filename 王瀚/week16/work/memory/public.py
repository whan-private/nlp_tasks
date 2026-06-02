from werewolf.core.event_bus import Event, EventType


class PublicMemory:
    def __init__(self):
        self.day_messages: list[dict] = []
        self.vote_records: list[dict] = []
        self.elimination_records: list[dict] = []
        self.night_announcements: list[dict] = []

    def add_event(self, event: Event):
        if not event.is_public():
            return
        if event.type == EventType.PUBLIC_SPEECH:
            self.day_messages.append(event.data)
        elif event.type == EventType.VOTE_CAST:
            self.vote_records.append(event.data)
        elif event.type == EventType.VOTE_RESULT:
            pass
        elif event.type == EventType.PLAYER_ELIMINATED:
            self.elimination_records.append(event.data)
        elif event.type == EventType.SYSTEM:
            self.night_announcements.append(event.data)

    def get_chat_history(self, day: int | None = None) -> str:
        lines = []
        for msg in self.day_messages:
            pid = msg.get("player_id", "?")
            name = msg.get("player_name", f"P{pid}")
            content = msg.get("content", "")
            if msg.get("is_last_words"):
                lines.append(f"[Last Words] {name}: {content}")
            else:
                lines.append(f"{name}: {content}")
        return "\n".join(lines)

    def get_vote_summary(self) -> str:
        lines = []
        for v in self.vote_records:
            lines.append(f"{v['voter_name']} voted for {v['target_name']}")
        return "\n".join(lines)

    def get_death_history(self) -> str:
        lines = []
        for e in self.elimination_records:
            lines.append(f"{e['player_name']} ({e['reason']}) was {e['role']}")
        return "\n".join(lines)

    def get_alive_players(self, state) -> list[str]:
        return [p.name for p in state.alive_players]
