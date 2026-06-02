class PrivateMemory:
    def __init__(self, player_id: int, role: str):
        self.player_id = player_id
        self.role = role
        self.notes: list[str] = []
        self.deductions: list[str] = []
        self.night_results: list[dict] = []

    def add_note(self, note: str):
        self.notes.append(note)

    def add_deduction(self, deduction: str):
        self.deductions.append(deduction)

    def add_night_result(self, result: dict):
        self.night_results.append(result)

    def get_deduction_history(self) -> str:
        if not self.deductions:
            return "No deductions yet."
        return "\n".join(f"- {d}" for d in self.deductions[-5:])

    def get_night_summary(self) -> str:
        if not self.night_results:
            return "No night actions yet."
        lines = []
        for nr in self.night_results:
            lines.append(f"Round {nr.get('round', '?')}: {nr.get('description', '')}")
        return "\n".join(lines)
