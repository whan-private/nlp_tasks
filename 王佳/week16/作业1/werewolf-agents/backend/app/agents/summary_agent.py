"""总结 Agent — 在每局游戏结束后，为每种角色生成对局总结并保存为可复用的经验。"""

import json
import re

from openai import AsyncOpenAI

from app.core.config import get_settings

settings = get_settings()

# 角色中文名
ROLE_NAMES = {
    "werewolf": "狼人",
    "seer": "预言家",
    "witch": "女巫",
    "hunter": "猎人",
    "villager": "村民",
}


class SummaryAgent:
    """游戏总结 Agent — 对每种参与角色生成结构化复盘总结。"""

    def __init__(self, memory_service=None):
        from app.services.memory_service import memory_service as ms

        self.memory = memory_service or ms
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        )

    async def summarize_game(
        self,
        game_id: str,
        game_logs: list[dict],
        players: list[dict],
        winner: str,
    ) -> list[dict]:
        """为游戏中的每种角色生成总结。

        Args:
            game_id: 游戏 ID
            game_logs: 完整的游戏事件日志列表
            players: 所有玩家信息 [{id, role, team, is_alive?}, ...]
            winner: 胜者阵营 (werewolf/villager)

        Returns:
            [{role, summary, lessons, key_moments, won}, ...]
        """
        # 去重：只取每种角色生成一份总结（同角色不同玩家共享同一份经验）
        roles_in_game = list(dict.fromkeys(p["role"] for p in players))
        results = []

        for role in roles_in_game:
            entry = await self._summarize_role(game_id, role, game_logs, players, winner)
            if entry:
                results.append(entry)

        return results

    async def _summarize_role(
        self,
        game_id: str,
        role: str,
        game_logs: list[dict],
        players: list[dict],
        winner: str,
    ) -> dict | None:
        """为单个角色生成对局总结。"""
        # 判断该角色阵营是否获胜
        from app.services.role_system import ROLE_REGISTRY

        role_cls = ROLE_REGISTRY.get(role)
        role_team = role_cls().team.value if role_cls else "villager"
        won = (winner == role_team)

        # 构建 LLM 上下文
        role_cn = ROLE_NAMES.get(role, role)
        prompt = self._build_summary_prompt(role_cn, role, game_logs, players, won)

        # 调用 LLM 生成总结
        summary_json = await self._call_llm(prompt)
        if not summary_json:
            return None

        summary = summary_json.get("summary", "")
        lessons = summary_json.get("lessons", [])
        key_moments = summary_json.get("key_moments", [])

        # 保存经验到记忆库
        self.memory.save_experience(
            role=role,
            game_id=game_id,
            summary=summary,
            lessons=lessons,
            key_moments=key_moments,
            won=won,
        )

        return {
            "role": role,
            "role_cn": role_cn,
            "summary": summary,
            "lessons": lessons,
            "key_moments": key_moments,
            "won": won,
        }

    def _build_summary_prompt(
        self,
        role_cn: str,
        role: str,
        game_logs: list[dict],
        players: list[dict],
        won: bool,
    ) -> str:
        """构建总结提示词。"""
        outcome = "胜利" if won else "失败"

        # 格式化游戏日志
        log_text_parts = []
        for log in game_logs:
            event = log.get("event", "")
            message = log.get("message", "")
            data = log.get("data", {})
            log_text_parts.append(f"[{event}] {message}")
            if data:
                log_text_parts.append(f"  详情: {json.dumps(data, ensure_ascii=False)}")
        log_text = "\n".join(log_text_parts[-80:])  # 最新的80行

        # 格式化玩家信息
        player_text_parts = []
        role_team = "werewolf" if role == "werewolf" else "villager"
        for p in players:
            p_team = p.get("team", "?")
            marker = " <- 你的阵营" if p_team == role_team else ""
            player_text_parts.append(
                f"- {p['id'][:6]} | {ROLE_NAMES.get(p.get('role', ''), p.get('role', ''))} | "
                f"阵营:{p_team}{marker}"
            )
        player_text = "\n".join(player_text_parts)

        return f"""你是一位狼人杀策略分析师。一局游戏刚刚结束，请从 **{role_cn}** 角色的视角进行复盘总结。

## 游戏结果
{role_cn}所在阵营 **{outcome}**。

## 玩家列表
{player_text}

## 游戏日志
{log_text}

## 总结要求
请从 {role_cn} 的视角出发，用中文总结本局游戏。输出严格按以下 JSON 格式：

```json
{{
  "summary": "一段 150-300 字的总结，包括：该角色在本局的关键行为、决策质量、对胜负的影响",
  "lessons": [
    "经验教训1（具体、可操作的建议）",
    "经验教训2",
    "经验教训3"
  ],
  "key_moments": [
    "关键转折点1（如：第X轮投票放逐了关键角色）",
    "关键转折点2"
  ]
}}
```

注意：
- summary 要简洁有洞察，不流水账
- lessons 要具体可操作，其他 {role_cn} 玩家在后续对局中可以直接参考
- key_moments 要指出影响胜负的关键事件"""

    async def _call_llm(self, prompt: str) -> dict | None:
        """调用 LLM 并解析 JSON 结果。"""
        try:
            response = await self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=800,
            )
            text = response.choices[0].message.content
            if not text:
                return None
            return self._parse_json(text)
        except Exception as e:
            import logging
            logging.getLogger("werewolf").error(f"SummaryAgent LLM 调用失败: {e}")
            return None

    def _parse_json(self, text: str) -> dict | None:
        """容错 JSON 解析。"""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        return None
