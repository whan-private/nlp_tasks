import asyncio
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services.agent_manager import AgentManager
from app.services.role_system import (
    ActionType,
    Hunter,
    Phase,
    Team,
    get_night_action_order,
)
from app.services.memory_service import memory_service
from app.services.sse_service import sse_manager
from app.utils.logger import logger as base_logger

settings = get_settings()
logger = base_logger


class GameEngine:
    """游戏引擎 — 支持自动/手动两种模式，支持暂停/恢复/停止/单步执行。"""

    def __init__(self, game_id: str, agent_manager: AgentManager, mode: str = "auto"):
        self.game_id = game_id
        self.am = agent_manager
        self.round = 1
        self.phase = Phase.NIGHT
        self.state: dict = {}
        self.logs: list[dict] = []
        self.winner: str | None = None
        self._pending_hunter_shots: list[str] = []

        # ---- 控制 ----
        self._pause_event = asyncio.Event()
        self._pause_event.set()       # 初始非暂停
        self._stopped = False
        self._step_mode = False       # 单步触发（一次性）
        self._mode = mode             # "auto" | "manual"

        self.llm_client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            timeout=60.0,
        )

    # ==================== 控制接口 ====================

    def pause(self):
        self._pause_event.clear()

    def resume(self):
        self._step_mode = False
        self._pause_event.set()

    def stop(self):
        self._stopped = True
        self._step_mode = False
        self._pause_event.set()  # 解除阻塞以让循环检查 stopped

    def step(self):
        """单步执行：如果是手动模式，推进到下一个检查点后自动暂停。"""
        self._step_mode = True
        self._pause_event.set()

    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str):
        """切换模式：auto（自动运行到底）/ manual（每阶段暂停等待手动推进）。"""
        if mode not in ("auto", "manual"):
            raise ValueError("mode 必须是 auto 或 manual")
        self._mode = mode
        if mode == "manual":
            # 切换到手动模式时立即暂停
            self.pause()
        else:
            # 切换到自动模式时清除 step_mode 并继续
            self._step_mode = False
            self.resume()

    @property
    def is_paused(self) -> bool:
        return not self._pause_event.is_set()

    @property
    def is_running(self) -> bool:
        return not self._stopped and not self.is_paused

    async def _check_control(self):
        """在循环关键点调用：等待暂停解除，检测停止标志。

        手动模式下，如果之前触发了 step()，通过一个检查点后自动重新暂停。
        """
        self._save_checkpoint()
        await self._pause_event.wait()
        if self._stopped:
            raise GameStoppedError()
        # 手动模式 + 单步触发：通过一个检查点后立即重新暂停
        if self._mode == "manual" and self._step_mode:
            self._step_mode = False
            self._pause_event.clear()
            await self._emit("phase_paused", {
                "round": self.round,
                "phase": self.phase.value,
                "phase_details": self.state.get("phase_details", {}),
            })

    def _save_checkpoint(self):
        """将引擎完整状态持久化到数据库，用于断点续玩。"""
        try:
            db = SessionLocal()
            from app.models.game import Game as GameModel
            game = db.query(GameModel).filter(GameModel.id == self.game_id).first()
            if game:
                game.round = self.round
                game.phase = self.phase.value
                # 收集需要持久化的 agent 状态（女巫药水、猎人开枪能力等）
                agent_states = {}
                for pid, ctx in self.am.agents.items():
                    from app.services.role_system import Hunter, Witch
                    agent_state = {}
                    if isinstance(ctx.role, Witch):
                        agent_state["antidote_used"] = ctx.role.antidote_used
                        agent_state["poison_used"] = ctx.role.poison_used
                    if isinstance(ctx.role, Hunter):
                        agent_state["can_shoot"] = ctx.role.can_shoot
                    if agent_state:
                        agent_states[pid] = agent_state
                game.engine_state = {
                    "state": self.state,
                    "logs": [
                        {"timestamp": log.get("timestamp", ""), "event": log.get("event", ""),
                         "message": log.get("message", ""), "data": log.get("data", {})}
                        for log in self.logs[-200:]
                    ],
                    "pending_hunter_shots": self._pending_hunter_shots,
                    "agent_states": agent_states,
                }
                db.commit()
            db.close()
        except Exception as e:
            logger.error(f"保存检查点失败: {e}")

    def _load_checkpoint(self, saved: dict):
        """从数据库加载状态恢复引擎。"""
        self.round = saved.get("round", 1)
        phase_str = saved.get("phase", "night")
        self.phase = Phase.NIGHT if phase_str == "night" else Phase.DAY
        self._mode = saved.get("config", {}).get("mode", "auto")
        if isinstance(self._mode, dict):
            self._mode = self._mode.get("mode", "auto")

        es = saved.get("engine_state", {})
        if es:
            self.state = es.get("state", {})
            self.logs = es.get("logs", [])
            self._pending_hunter_shots = es.get("pending_hunter_shots", [])

            # 恢复 agent 状态
            agent_states = es.get("agent_states", {})
            for pid, agent_state in agent_states.items():
                ctx = self.am.get_agent(pid)
                if ctx:
                    from app.services.role_system import Hunter, Witch
                    if isinstance(ctx.role, Witch):
                        ctx.role.antidote_used = agent_state.get("antidote_used", False)
                        ctx.role.poison_used = agent_state.get("poison_used", False)
                    if isinstance(ctx.role, Hunter):
                        ctx.role.can_shoot = agent_state.get("can_shoot", True)

    # ==================== 公共状态 ====================

    def get_public_state(self) -> dict:
        """返回当前游戏的公开状态（用于 API 响应）。"""
        return {
            "game_id": self.game_id,
            "round": self.round,
            "phase": self.phase.value,
            "mode": self._mode,
            "is_paused": self.is_paused,
            "is_running": self.is_running,
            "winner": self.winner,
            "alive_players": [
                {"id": p["id"], "name": p.get("name", ""), "role": p.get("role", "unknown"), "team": p["team"]}
                for p in self.state.get("alive_players", [])
            ],
            "dead_players": self.state.get("dead_players", []),
            "public_logs": self.state.get("public_logs", []),
            "phase_details": self.state.get("phase_details", {}),
            "recent_logs": [
                {"timestamp": log.get("timestamp", ""), "event": log.get("event", ""),
                 "message": log.get("message", "")}
                for log in self.logs[-60:]
            ],
        }

    def get_result(self) -> dict:
        """返回游戏最终结果。"""
        return {
            "game_id": self.game_id,
            "winner": self.winner,
            "total_rounds": self.round,
            "players": self.state.get("alive_players", []) + self.state.get("dead_players", []),
            "logs": [
                {"timestamp": log["timestamp"], "event": log.get("event", ""), "message": log["message"]}
                for log in self.logs
            ],
        }

    # ==================== 辅助 ====================

    def _is_alive(self, player_id: str) -> bool:
        return any(p["id"] == player_id for p in self.state.get("alive_players", []))

    def _kill_player(self, player_id: str, cause: str):
        """将玩家从存活移到死亡列表，保留 name/role/team 信息。"""
        for p in self.state.get("alive_players", []):
            if p["id"] == player_id:
                self.state["alive_players"].remove(p)
                self.state.setdefault("dead_players", []).append({
                    "player_id": player_id,
                    "name": p.get("name", ""),
                    "role": p.get("role", "unknown"),
                    "team": p.get("team", "unknown"),
                    "cause": cause,
                })
                return

    def _extract_action(self, decision: dict) -> dict:
        return decision.get("action", decision)

    # ==================== 游戏主循环 ====================

    async def run(self, player_roles: dict[str, dict], resume: bool = False):
        """启动游戏主循环。

        Args:
            player_roles: {player_id: {"role": ..., "name": ...}}
            resume: True 表示从数据库 checkpoint 恢复，False 表示新游戏
        """
        try:
            self.am.create_agents({pid: info["role"] for pid, info in player_roles.items()})
            players_info = [
                {"id": pid, "name": info["name"], "role": info["role"], "team": ctx.team.value}
                for pid, info in player_roles.items()
                if (ctx := self.am.get_agent(pid))
            ]

            if resume:
                # 从数据库加载之前保存的状态
                try:
                    db = SessionLocal()
                    from app.models.game import Game as GameModel
                    saved = db.query(GameModel).filter(GameModel.id == self.game_id).first()
                    if saved and saved.engine_state:
                        self._load_checkpoint({
                            "round": saved.round,
                            "phase": saved.phase,
                            "config": saved.config,
                            "engine_state": saved.engine_state,
                        })
                        # 从恢复的状态中获取存活/死亡玩家列表
                        alive = self.state.get("alive_players", [])
                        dead = self.state.get("dead_players", [])
                        players_info = [
                            {"id": p["id"], "name": p.get("name", ""), "role": p.get("role", "unknown"),
                             "team": p.get("team", "unknown")}
                            for p in alive
                        ]
                        db.close()
                        self._log("游戏从断点恢复", event="game_resumed",
                                  data={"round": self.round, "phase": self.phase.value})
                        # 将死亡玩家同步到 agent_manager
                        for d in dead:
                            self.am.mark_dead(d.get("player_id", ""))
                except Exception as e:
                    logger.error(f"加载检查点失败，从头开始: {e}")
                    resume = False

            if not resume:
                self.state = {
                    "alive_players": [p for p in players_info],
                    "dead_players": [],
                    "public_logs": [],
                    "werewolf_discussion": [],
                    "seer_checks": {},
                    "night_kill_target": None,
                    "phase_details": {},
                }
                self._pending_hunter_shots = []

            await self._emit("game_start", {"players": players_info, "resumed": resume})
            self._log("游戏开始" if not resume else f"游戏恢复 (第{self.round}轮 {self.phase.value})",
                      event="game_start", data={"players": players_info, "resumed": resume})

            # 如果是恢复模式，跳过已完成的阶段，从保存的阶段开始
            if resume:
                if self.phase == Phase.DAY:
                    # 夜晚已完成，跳到白天
                    self.state["round"] = self.round
                    self.state["phase_details"] = {"type": "day", "round": self.round, "stage": "announce"}
                    await self._emit("round_start", {"round": self.round, "phase": "day"})
                    self._log(f"第 {self.round} 轮 白天 开始 (恢复)", round=self.round, phase="day")
                    await self._day_phase()
                    if not self._check_win():
                        self.round += 1
                elif self.phase == Phase.NIGHT:
                    # 从夜晚开始
                    self.state["round"] = self.round
                    self.state["phase_details"] = {"type": "night", "round": self.round}
                    await self._emit("round_start", {"round": self.round, "phase": "night"})
                    self._log(f"第 {self.round} 轮 夜晚 开始 (恢复)", round=self.round, phase="night")
                    await self._night_phase()
                    if not self._check_win():
                        # 继续到白天
                        self.phase = Phase.DAY
                        self.state["phase_details"] = {"type": "day", "round": self.round, "stage": "announce"}
                        await self._check_control()
                        await self._emit("round_start", {"round": self.round, "phase": "day"})
                        self._log(f"第 {self.round} 轮 白天 开始", round=self.round, phase="day")
                        await self._day_phase()
                        if not self._check_win():
                            self.round += 1

            # 如果已经结束（在 resume 的 _day_phase 中分出了胜负），跳过主循环
            if self.winner:
                pass
            else:
                # 主循环：从当前 round 继续
                while True:
                    # === 夜晚 ===
                    self.phase = Phase.NIGHT
                    self.state["round"] = self.round
                    self.state["phase_details"] = {"type": "night", "round": self.round}

                    await self._check_control()
                    await self._emit("round_start", {"round": self.round, "phase": "night"})
                    self._log(f"第 {self.round} 轮 夜晚 开始", round=self.round, phase="night")

                    await self._night_phase()
                    if self._check_win():
                        break

                    # === 白天 ===
                    self.phase = Phase.DAY
                    self.state["phase_details"] = {"type": "day", "round": self.round, "stage": "announce"}

                    await self._check_control()
                    await self._emit("round_start", {"round": self.round, "phase": "day"})
                    self._log(f"第 {self.round} 轮 白天 开始", round=self.round, phase="day")

                    await self._day_phase()
                    if self._check_win():
                        break

                    self.round += 1

            # 结束
            await self._emit("game_end", {"winner": self.winner, "round": self.round})
            self._log("游戏结束", event="game_end", data={"winner": self.winner})

            # ---- 总结阶段 ----
            await self._summary_phase(players_info)

            self._save_game_result()
            sse_manager.cleanup(self.game_id)

        except GameStoppedError:
            await self._emit("game_stopped", {"game_id": self.game_id, "round": self.round})
            self._log("游戏被手动停止", event="game_stopped")
            # 如果进行了至少一轮，仍然生成总结
            if self.round > 1 and len(self.logs) > 5:
                await self._summary_phase(players_info)
            self._save_game_result()
            sse_manager.cleanup(self.game_id)

    async def _night_phase(self):
        self.state["phase_details"] = {"type": "night", "stage": "werewolf", "round": self.round}
        night_actions = []
        acting_roles = get_night_action_order([ctx.role for ctx in self.am.agents.values()])

        for role in acting_roles:
            await self._check_control()
            if role.name == "werewolf":
                action = await self._werewolf_night()
            elif role.name == "seer":
                action = await self._seer_night()
            elif role.name == "witch":
                action = await self._witch_night()
            else:
                action = None
            if action:
                night_actions.append(action)

        self.state["phase_details"] = {"type": "night", "stage": "resolve", "round": self.round}
        self._resolve_night(night_actions)

    async def _werewolf_night(self) -> dict | None:
        werewolves = self.am.get_agents_by_role("werewolf")
        alive_wolves = [w for w in werewolves if self._is_alive(w.player_id)]
        if not alive_wolves:
            return None

        votes = {}
        for wolf in alive_wolves:
            await self._check_control()
            visible = self.am.build_visible_info(wolf.player_id, self.state)
            prompt = self._load_prompt("werewolf")
            context = self._build_context(prompt, visible, action_type="kill")
            decision = await self._call_llm(context)
            if decision:
                votes[wolf.player_id] = decision

        targets = [self._extract_action(d).get("target_id") for d in votes.values()]
        targets = [t for t in targets if t]
        if not targets:
            return None

        kill_target = Counter(targets).most_common(1)[0][0]
        self.state["night_kill_target"] = kill_target
        self.state["werewolf_discussion"] = [
            {"wolf_id": wid, "target_id": self._extract_action(d).get("target_id")}
            for wid, d in votes.items()
        ]

        for wid, d in votes.items():
            target = self._extract_action(d).get("target_id", "")
            self._save_action(wid, ActionType.KILL.value, target)

        action = {"actor": "werewolf_team", "type": ActionType.KILL.value, "target_id": kill_target}
        self._log(f"狼人团队决定击杀 {kill_target}", event="werewolf_kill", data=action,
                  visible_to=[w.player_id for w in alive_wolves])
        return action

    async def _seer_night(self) -> dict | None:
        seers = self.am.get_agents_by_role("seer")
        alive_seers = [s for s in seers if self._is_alive(s.player_id)]
        if not alive_seers:
            return None
        seer = alive_seers[0]

        visible = self.am.build_visible_info(seer.player_id, self.state)
        prompt = self._load_prompt("seer")
        decision = await self._call_llm(self._build_context(prompt, visible, action_type="check"))
        if not decision:
            return None

        act = self._extract_action(decision)
        target_id = act.get("target_id")
        if not target_id:
            return None

        check_result = "unknown"
        target_ctx = self.am.get_agent(target_id)
        if target_ctx:
            check_result = target_ctx.team.value
            self.state["seer_checks"][target_id] = check_result

        action = {"actor": seer.player_id, "type": ActionType.CHECK.value, "target_id": target_id, "result": check_result}
        self._log(f"预言家查验 {target_id} → {action['result']}", event="seer_check", data=action, visible_to=[seer.player_id])
        self._save_action(seer.player_id, ActionType.CHECK.value, target_id)
        return action

    async def _witch_night(self) -> dict | None:
        witches = self.am.get_agents_by_role("witch")
        alive_witches = [w for w in witches if self._is_alive(w.player_id)]
        if not alive_witches:
            return None
        witch = alive_witches[0]

        visible = self.am.build_visible_info(witch.player_id, self.state)
        prompt = self._load_prompt("witch")
        kill_info = ""
        if self.state.get("night_kill_target"):
            kill_info = f"**今晚狼人的击杀目标是: {self.state['night_kill_target']}**"
            if not witch.role.can_save():
                kill_info += "\n(解药已使用)"
            if not witch.role.can_poison():
                kill_info += "\n(毒药已使用)"

        decision = await self._call_llm(self._build_context(prompt, visible, action_type="save", extra_info=kill_info))
        if not decision:
            return None

        act = self._extract_action(decision)
        action_type = act.get("type", "skip")
        action = {"actor": witch.player_id, "type": action_type, "target_id": act.get("target_id")}

        if action_type == "save" and witch.role.can_save():
            witch.role.use_antidote()
            self._log("女巫使用了解药", event="witch_save", data=action)
            self._save_action(witch.player_id, ActionType.SAVE.value, act.get("target_id"))
        elif action_type == "poison" and witch.role.can_poison():
            witch.role.use_poison()
            self._log("女巫使用了毒药", event="witch_poison", data=action)
            self._save_action(witch.player_id, ActionType.POISON.value, act.get("target_id"))
        else:
            self._log("女巫选择不使用药水", event="witch_skip", data=action)
            self._save_action(witch.player_id, "skip", None)
        return action

    def _resolve_night(self, night_actions: list[dict]):
        deaths = []
        saved_player = None
        for a in night_actions:
            if a["type"] == ActionType.SAVE.value:
                saved_player = a.get("target_id")

        for a in night_actions:
            if a["type"] == ActionType.KILL.value:
                target = a["target_id"]
                if target != saved_player:
                    deaths.append({"player_id": target, "cause": "werewolf_kill", "can_hunter_shoot": True})

        for a in night_actions:
            if a["type"] == ActionType.POISON.value:
                target = a["target_id"]
                if target:
                    tctx = self.am.get_agent(target)
                    if tctx and isinstance(tctx.role, Hunter):
                        tctx.role.disable_shoot()
                    deaths.append({"player_id": target, "cause": "witch_poison", "can_hunter_shoot": False})

        saved_msg = f"，但 {saved_player} 被女巫救活" if saved_player else ""
        self._log(f"夜晚结果：{len(deaths)} 人死亡{saved_msg}", event="night_result",
                  data={"deaths": deaths, "saved": saved_player})

        self._pending_hunter_shots = []
        for d in deaths:
            if d.get("can_hunter_shoot"):
                ctx = self.am.get_agent(d["player_id"])
                if ctx and isinstance(ctx.role, Hunter) and ctx.role.can_shoot:
                    self._pending_hunter_shots.append(d["player_id"])

        self.state["night_deaths"] = deaths
        self.state["night_saved"] = saved_player
        self.state["phase_details"] = {"type": "night", "stage": "resolved", "deaths": deaths, "saved": saved_player}

    async def _day_phase(self):
        deaths = self.state.get("night_deaths", [])
        saved = self.state.get("night_saved")
        death_ids = [d["player_id"] for d in deaths]

        self.state["phase_details"] = {"type": "day", "stage": "announce", "deaths": death_ids, "saved": saved}
        await self._check_control()
        await self._emit("day_start", {"round": self.round, "deaths": death_ids, "saved": saved})
        self._log(f"天亮了，死亡: {death_ids}", event="day_start")

        for death in deaths:
            self._kill_player(death["player_id"], death["cause"])

        if self._check_win():
            return

        # 猎人夜间被杀 → 开枪
        for hunter_id in self._pending_hunter_shots:
            if self._is_alive(hunter_id):
                continue
            ctx = self.am.get_agent(hunter_id)
            if ctx and isinstance(ctx.role, Hunter) and ctx.role.can_shoot:
                await self._hunter_shoot(hunter_id)
        self._pending_hunter_shots = []

        if self._check_win():
            return

        # ---- 发言 ----
        self.state["phase_details"] = {"type": "day", "stage": "speaking", "round": self.round}
        alive = self.state["alive_players"]
        for player in alive:
            await self._check_control()
            ctx = self.am.get_agent(player["id"])
            if not ctx:
                continue
            visible = self.am.build_visible_info(player["id"], self.state)
            prompt = self._load_prompt(ctx.role_name)
            decision = await self._call_llm(self._build_context(prompt, visible, action_type="speak"))
            act = self._extract_action(decision) if decision else {}
            speech = act.get("content") or (decision or {}).get("content") or "（沉默）"
            await self._emit("player_speak", {"speaker": player["id"], "content": speech})
            self._log(f"玩家 {player['id']} 发言: {speech[:200]}", event="player_speak",
                      data={"speaker": player["id"], "content": speech})
            self._save_action(player["id"], "speak", None, speech[:500])
            self.state["public_logs"].append({"round": self.round, "speaker": player["id"], "content": speech})

        # ---- 投票 ----
        self.state["phase_details"] = {"type": "day", "stage": "voting", "round": self.round}
        votes = {}
        for player in alive:
            await self._check_control()
            ctx = self.am.get_agent(player["id"])
            if not ctx:
                continue
            visible = self.am.build_visible_info(player["id"], self.state)
            prompt = self._load_prompt(ctx.role_name)
            decision = await self._call_llm(self._build_context(prompt, visible, action_type="vote"))
            if decision:
                act = self._extract_action(decision)
                if act.get("target_id"):
                    votes[player["id"]] = act["target_id"]
                    self._save_action(player["id"], "vote", act["target_id"])

        if not votes:
            self._log("本轮无人投票", event="vote_result")
            return

        await self._check_control()
        vote_counts = Counter(votes.values())
        await self._emit("vote_result", {"votes": votes, "counts": dict(vote_counts)})
        self._log("投票结果", event="vote_result", data={"votes": votes, "counts": dict(vote_counts)})

        eliminated_id = vote_counts.most_common(1)[0][0]
        eliminated_ctx = self.am.get_agent(eliminated_id)
        self.state["phase_details"] = {"type": "day", "stage": "eliminated", "player_id": eliminated_id}

        self._log(f"玩家 {eliminated_id} 被投票放逐", event="player_eliminated",
                  data={"player_id": eliminated_id, "cause": "vote"})
        await self._emit("player_eliminated", {"player_id": eliminated_id, "cause": "vote"})
        self._kill_player(eliminated_id, "vote")

        if eliminated_ctx and isinstance(eliminated_ctx.role, Hunter) and eliminated_ctx.role.can_shoot:
            await self._check_control()
            await self._hunter_shoot(eliminated_id)

    async def _hunter_shoot(self, hunter_id: str):
        ctx = self.am.get_agent(hunter_id)
        if not ctx or not ctx.role.can_shoot:
            return

        alive_targets = [p for p in self.state["alive_players"] if p["id"] != hunter_id]
        if not alive_targets:
            return

        visible = self.am.build_visible_info(hunter_id, self.state)
        prompt = self._load_prompt("hunter")
        decision = await self._call_llm(self._build_context(prompt, visible, action_type="shoot"))
        if not decision:
            return

        act = self._extract_action(decision)
        target_id = act.get("target_id")
        if not target_id:
            self._log("猎人选择不开枪", event="hunter_skip")
            self._save_action(hunter_id, "shoot", None)
            return

        await self._emit("player_death", {"player_id": target_id, "cause": "hunter_shoot"})
        self._log(f"猎人开枪带走了 {target_id}", event="hunter_shoot",
                  data={"hunter_id": hunter_id, "target_id": target_id})
        self._save_action(hunter_id, "shoot", target_id)
        self._kill_player(target_id, "hunter_shoot")

    # ==================== 总结阶段 ====================

    async def _summary_phase(self, players_info: list[dict]):
        """游戏结束后的总结阶段：为每种角色生成对局总结并保存经验。"""
        try:
            from app.agents.summary_agent import SummaryAgent

            await self._emit("summary_start", {"game_id": self.game_id})
            self._log("开始生成对局总结...", event="summary_start")

            agent = SummaryAgent()

            # 将 logs 转换为列表格式供 SummaryAgent 使用
            log_dicts = [
                {"event": log.get("event", ""), "message": log.get("message", ""),
                 "data": log.get("data", {}) if isinstance(log.get("data"), dict) else {}}
                for log in self.logs
            ]

            summaries = await agent.summarize_game(
                game_id=self.game_id,
                game_logs=log_dicts,
                players=players_info,
                winner=self.winner or "",
            )

            for s in summaries:
                await self._emit("game_summary", {
                    "role": s["role"],
                    "role_cn": s["role_cn"],
                    "summary": s["summary"],
                    "lessons": s["lessons"],
                    "key_moments": s["key_moments"],
                    "won": s["won"],
                })
                self._log(
                    f"{s['role_cn']} 总结: {s['summary'][:100]}...",
                    event="game_summary",
                    data=s,
                )

            await self._emit("summary_complete", {
                "roles_summarized": [s["role"] for s in summaries],
            })
            self._log("所有角色总结完成", event="summary_complete")

        except Exception as e:
            logger.error(f"总结阶段失败: {e}")
            await self._emit("summary_complete", {"error": str(e)})

    # ==================== 通用方法 ====================

    def _check_win(self) -> bool:
        alive = self.state["alive_players"]
        wc = sum(1 for p in alive if p["team"] == Team.WEREWOLF.value)
        vc = sum(1 for p in alive if p["team"] == Team.VILLAGER.value)
        if wc == 0:
            self.winner = Team.VILLAGER.value
            return True
        if wc >= vc:
            self.winner = Team.WEREWOLF.value
            return True
        return False

    async def _call_llm(self, context: str) -> dict | None:
        try:
            response = await self.llm_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": context}],
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
            )
            text = response.choices[0].message.content
            return self._parse_json(text) if text else None
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            return None

    def _parse_json(self, text: str) -> dict | None:
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

    def _load_prompt(self, role_name: str) -> str:
        prompt_dir = Path(__file__).parent.parent / "prompts"
        prompt_file = prompt_dir / f"{role_name}.txt"
        return prompt_file.read_text(encoding="utf-8") if prompt_file.exists() else ""

    def _build_context(self, prompt: str, visible: dict, action_type: str, extra_info: str = "") -> str:
        role_name = visible.get("role_name", "")
        parts = [prompt, "",
                 "## 当前游戏状态",
                 f"- 轮次: 第 {visible.get('round', 0)} 轮",
                 f"- 阶段: {visible.get('phase', '')}",
                 f"- 你的角色: {role_name}",
                 f"- 存活玩家: {[p['id'] for p in visible.get('alive_players', [])]}",
                 f"- 已死亡玩家: {visible.get('dead_players', [])}"]
        if visible.get("extra"):
            parts.append("")
            parts.append("## 你的专属信息")
            for k, v in visible["extra"].items():
                parts.append(f"- {k}: {v}")
        if visible.get("public_logs"):
            parts.append("")
            parts.append("## 公开日志（发言记录）")
            for log in visible["public_logs"][-10:]:
                parts.append(f"- [第{log['round']}轮] {log['speaker']}: {log['content'][:200]}")

        # ---- 注入历史经验 ----
        past = memory_service.format_for_prompt(role_name, limit=3) if role_name else ""
        if past:
            parts.append("")
            parts.append(past)

        if extra_info:
            parts.append("")
            parts.append(extra_info)
        parts.append("")
        parts.append(f"## 请做出 {action_type} 决策")
        parts.append("请以 JSON 格式输出你的决策。")
        return "\n".join(parts)

    async def _emit(self, event: str, data: dict):
        await sse_manager.emit(self.game_id, event, data)

    def _save_game_result(self):
        from app.models.game import Game as GameModel
        try:
            db = SessionLocal()
            game = db.query(GameModel).filter(GameModel.id == self.game_id).first()
            if game:
                game.status = "finished"
                game.winner = self.winner
                game.finished_at = datetime.now(timezone.utc)
                game.engine_state = None  # 清除检查点
                db.commit()
            db.close()
        except Exception as e:
            logger.error(f"持久化游戏结果失败: {e}")

    def _log(self, message: str, **kwargs):
        extra = {"game_id": self.game_id, "round": self.round, "phase": self.phase.value}
        extra.update(kwargs)
        logger.info(message, extra=extra)
        log_entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "message": message, **extra}
        self.logs.append(log_entry)

        # 持久化到 game_logs 表
        try:
            db = SessionLocal()
            from app.models.log import GameLog
            db.add(GameLog(
                game_id=self.game_id,
                round=self.round,
                phase=self.phase.value,
                event=kwargs.get("event", ""),
                data=kwargs.get("data", {}),
                visible_to=kwargs.get("visible_to"),
            ))
            db.commit()
            db.close()
        except Exception as e:
            logger.error(f"持久化游戏日志失败: {e}")

    def _save_action(self, actor_id: str, action_type: str, target_id: str | None = None, content: str | None = None):
        """持久化玩家行动到 actions 表。"""
        try:
            db = SessionLocal()
            from app.models.action import Action
            db.add(Action(
                game_id=self.game_id,
                round=self.round,
                phase=self.phase.value,
                actor_id=actor_id,
                action_type=action_type,
                target_id=target_id,
                content=content,
            ))
            db.commit()
            db.close()
        except Exception as e:
            logger.error(f"持久化玩家行动失败: {e}")


class GameStoppedError(Exception):
    """游戏被手动停止。"""
    pass
