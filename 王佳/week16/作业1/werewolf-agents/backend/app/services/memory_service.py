"""角色经验记忆服务 — 持久化存储每局游戏的总结，供后续游戏参考。"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path


class MemoryService:
    """文件级经验记忆库，按角色分文件存储。

    目录结构：
        backend/memory/
            werewolf.json
            seer.json
            witch.json
            hunter.json
            villager.json
    """

    def __init__(self, base_dir: str | None = None):
        if base_dir:
            self._base = Path(base_dir)
        else:
            self._base = Path(__file__).parent.parent.parent / "memory"
        self._base.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._cache: dict[str, list[dict]] = {}

    # ---- 文件路径 ----

    def _file(self, role: str) -> Path:
        return self._base / f"{role}.json"

    # ---- 读写 ----

    def _load(self, role: str) -> list[dict]:
        """从磁盘加载某个角色的全部经验（带缓存）。"""
        if role in self._cache:
            return self._cache[role]
        path = self._file(role)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = []
        else:
            data = []
        self._cache[role] = data
        return data

    def _save(self, role: str, data: list[dict]):
        """持久化到磁盘并更新缓存。"""
        path = self._file(role)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._cache[role] = data

    # ---- 公开接口 ----

    def save_experience(
        self,
        role: str,
        game_id: str,
        summary: str,
        lessons: list[str],
        key_moments: list[str],
        won: bool,
    ):
        """保存一条角色经验。

        Args:
            role: 角色名 (werewolf/seer/witch/hunter/villager)
            game_id: 游戏 ID
            summary: 完整的总结文本（LLM 生成）
            lessons: 经验教训列表
            key_moments: 关键转折点列表
            won: 该角色所在阵营是否获胜
        """
        with self._lock:
            data = self._load(role)
            entry = {
                "game_id": game_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "role": role,
                "won": won,
                "summary": summary,
                "lessons": lessons,
                "key_moments": key_moments,
            }
            data.append(entry)
            self._save(role, data)

    def load_experiences(self, role: str, limit: int = 20) -> list[dict]:
        """加载某个角色的最近 N 条经验（最新的在前）。"""
        with self._lock:
            data = self._load(role)
        return list(reversed(data))[:limit]

    def format_for_prompt(self, role: str, limit: int = 5) -> str:
        """将历史经验格式化为可嵌入 prompt 的文本。

        Args:
            role: 角色名
            limit: 取最近 N 条经验

        Returns:
            格式化的经验文本，如果无经验则返回空字符串
        """
        experiences = self.load_experiences(role, limit)
        if not experiences:
            return ""

        lines = ["## 历史经验（来自往期对局）", ""]
        for i, exp in enumerate(experiences, 1):
            outcome = "胜利" if exp["won"] else "失败"
            lines.append(f"### 经验 {i}（{outcome}）")
            lines.append(exp["summary"])
            if exp.get("lessons"):
                lines.append("**教训:**")
                for lesson in exp["lessons"]:
                    lines.append(f"- {lesson}")
            lines.append("")
        return "\n".join(lines)

    def get_stats(self) -> dict:
        """获取经验库统计信息。"""
        stats = {}
        for role in ["werewolf", "seer", "witch", "hunter", "villager"]:
            data = self._load(role)
            wins = sum(1 for e in data if e.get("won"))
            stats[role] = {"total": len(data), "wins": wins}
        return stats


# 全局单例
memory_service = MemoryService()
