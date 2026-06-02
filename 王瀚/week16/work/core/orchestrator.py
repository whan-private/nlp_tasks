import random
from werewolf.core.game_state import GameState, Phase, Team
from werewolf.core.rule_engine import assign_roles, check_win_condition
from werewolf.core.event_bus import EventBus, Event, EventType
from werewolf.core.phase_manager import PhaseManager
from werewolf.core.logger import GameLogger
from werewolf.config import GameConfig
from werewolf.agents.base import BaseAgent
from werewolf.agents.factory import create_agents
from werewolf.llm.client import LLMClient


class Orchestrator:
    def __init__(self, config: GameConfig, player_names: list[str],
                 agents: dict[int, BaseAgent] | None = None,
                 llm_client: LLMClient | None = None,
                 use_mock: bool = False):
        self.config = config
        self.state = assign_roles(config, player_names)
        self.bus = EventBus()
        self.phase_manager = PhaseManager(self.state, self.bus)
        self.logger = GameLogger()
        self.use_mock = use_mock

        if agents:
            self.agents = agents
        elif llm_client and not use_mock:
            self.agents = create_agents(self.state, llm_client)
        else:
            self.agents = {}

        for event_type in EventType:
            self.bus.subscribe(event_type, self.logger.log)

        for agent in self.agents.values():
            self.bus.subscribe(EventType.PUBLIC_SPEECH, agent.on_event)
            self.bus.subscribe(EventType.VOTE_CAST, agent.on_event)
            self.bus.subscribe(EventType.VOTE_RESULT, agent.on_event)
            self.bus.subscribe(EventType.PLAYER_ELIMINATED, agent.on_event)
            self.bus.subscribe(EventType.PLAYER_DIED, agent.on_event)
            self.bus.subscribe(EventType.SYSTEM, agent.on_event)

        self._night_kill_target: int | None = None
        self._witch_save_target: int | None = None
        self._witch_poison_target: int | None = None
        self._seer_check_result: dict | None = None
        self._vote_counts: dict[int, int] = {}

    def run(self) -> dict:
        self.bus.publish(Event(EventType.SYSTEM, {
            "message": "Game started",
            "player_count": self.config.total_players,
            "roles": self.config.roles,
        }))

        while self.state.phase != Phase.GAME_OVER:
            self._run_current_phase()

        self.logger.log(Event(EventType.GAME_OVER, {
            "winner": self.state.winner.value if self.state.winner else "none",
            "alive_players": [(p.id, p.name, p.role) for p in self.state.alive_players],
            "dead_players": [(p.id, p.name, p.role) for p in self.state.dead_players],
        }))

        result = {
            "winner": self.state.winner.value if self.state.winner else "none",
            "rounds": self.state.round_num,
            "days": self.state.day_num,
            "eliminated": self.state.eliminated_history,
        }
        log_path = self.logger.save(game_result=result)
        result["log_path"] = log_path
        return result

    def _run_current_phase(self):
        phase = self.state.phase
        if phase == Phase.NIGHT_WEREWOLF:
            self._handle_werewolf_night()
        elif phase == Phase.NIGHT_SEER:
            self._handle_seer_night()
        elif phase == Phase.NIGHT_WITCH:
            self._handle_witch_night()
            self._resolve_night_deaths()
        elif phase == Phase.DAY_DISCUSSION:
            self._handle_day_discussion()
        elif phase == Phase.DAY_VOTE:
            self._handle_vote()
        elif phase == Phase.DAY_LAST_WORDS:
            self._handle_last_words()
        self.phase_manager.advance_phase()

    # ---- Night handlers ----

    def _handle_werewolf_night(self):
        alive_wolves = self.state.get_alive_wolves()
        targets = [p for p in self.state.alive_players if p.team == Team.VILLAGE]
        if not targets or not alive_wolves:
            self._night_kill_target = None
            return

        votes = {}
        for wolf in alive_wolves:
            agent = self.agents.get(wolf.id)
            if agent and not self.use_mock:
                decision = agent.night_action(self.state)
                tgt_name = decision.get("target", "")
            else:
                tgt_name = random.choice(targets).name

            tgt = self.state.get_player_by_name(tgt_name)
            if tgt and tgt.alive and tgt.team == Team.VILLAGE:
                votes[tgt.id] = votes.get(tgt.id, 0) + 1

        if votes:
            self._night_kill_target = max(votes, key=votes.get)
            killed = self.state.get_player(self._night_kill_target)
            self.bus.publish(Event(
                EventType.NIGHT_ACTION,
                {"actor_ids": [w.id for w in alive_wolves],
                 "target_id": self._night_kill_target,
                 "target_name": killed.name if killed else "?"},
                private_to=[w.id for w in alive_wolves],
            ))

    def _handle_seer_night(self):
        seers = [p for p in self.state.alive_players if p.role == "seer"]
        if not seers:
            return
        seer = seers[0]
        agent = self.agents.get(seer.id)

        others = [p for p in self.state.alive_players if p.id != seer.id]
        if not others:
            return

        decision = {"target": others[0].name}
        if agent and not self.use_mock:
            decision = agent.night_action(self.state)

        tgt = self.state.get_player_by_name(decision.get("target", ""))
        if not tgt or tgt.id == seer.id:
            tgt = others[0]

        check_result = tgt.team.value
        self._seer_check_result = {
            "actor_id": seer.id,
            "target_id": tgt.id,
            "target_name": tgt.name,
            "result": check_result,
        }
        self.bus.publish(Event(
            EventType.NIGHT_ACTION,
            self._seer_check_result,
            private_to=[seer.id],
        ))

    def _handle_witch_night(self):
        witches = [p for p in self.state.alive_players if p.role == "witch"]
        if not witches:
            return
        witch = witches[0]

        if self._night_kill_target is not None and self._night_kill_target != witch.id:
            killed = self.state.get_player(self._night_kill_target)
            self.bus.publish(Event(
                EventType.NIGHT_ACTION,
                {"data": {"target_id": self._night_kill_target,
                          "message": f"Tonight {killed.name} was attacked"}},
                private_to=[witch.id],
            ))

            agent = self.agents.get(witch.id)
            decision = {"save": True, "poison_target": None}
            if agent and not self.use_mock:
                decision = agent.night_action(self.state)

            if decision.get("save") and witch.witch_has_antidote:
                self._witch_save_target = self._night_kill_target

            poison_name = decision.get("poison_target")
            if poison_name:
                poison_tgt = self.state.get_player_by_name(poison_name)
                if poison_tgt and poison_tgt.alive and poison_tgt.id != witch.id and witch.witch_has_poison:
                    self._witch_poison_target = poison_tgt.id

    def _resolve_night_deaths(self):
        killed = set()
        if self._night_kill_target is not None:
            target = self.state.get_player(self._night_kill_target)
            if target and target.alive and not target.protected:
                if self._witch_save_target != self._night_kill_target:
                    target.killed_tonight = True
                    killed.add(self._night_kill_target)
                else:
                    target.witch_saved = True
                    witch = next((p for p in self.state.players if p.role == "witch"), None)
                    if witch:
                        witch.witch_has_antidote = False
                        self.bus.publish(Event(
                            EventType.SYSTEM,
                            {"message": f"Witch saved {target.name}"},
                        ))

        if self._witch_poison_target is not None:
            target = self.state.get_player(self._witch_poison_target)
            if target and target.alive:
                target.poisoned_tonight = True
                killed.add(self._witch_poison_target)
                witch = next((p for p in self.state.players if p.role == "witch"), None)
                if witch:
                    witch.witch_has_poison = False

        night_deaths = []
        for pid in killed:
            p = self.state.get_player(pid)
            if p:
                self.state.eliminate(pid, "killed_at_night")
                night_deaths.append({"id": p.id, "name": p.name})
                self.bus.publish(Event(
                    EventType.PLAYER_DIED,
                    {"player_id": p.id, "player_name": p.name, "reason": "killed_at_night",
                     "role": p.role},
                ))

        msg = f"Night passed. {len(night_deaths)} player(s) died."
        if not night_deaths:
            msg = "Night passed. No one died."
        self.bus.publish(Event(EventType.SYSTEM, {"message": msg}))

        self._night_kill_target = None
        self._witch_save_target = None
        self._witch_poison_target = None
        self._seer_check_result = None

    # ---- Day handlers ----

    def _handle_day_discussion(self):
        self.bus.publish(Event(EventType.SYSTEM, {
            "message": f"Day {self.state.day_num} begins. Discussion phase."
        }))

        for player in self.state.alive_players:
            agent = self.agents.get(player.id)
            text = "...(thinking)..."
            if agent and not self.use_mock:
                text = agent.make_speech(self.state)
            self.bus.publish(Event(
                EventType.PUBLIC_SPEECH,
                {"player_id": player.id, "player_name": player.name, "content": text},
            ))

    def _handle_vote(self):
        self.bus.publish(Event(EventType.SYSTEM, {"message": "Voting phase begins."}))

        self._vote_counts = {}
        for voter in self.state.alive_players:
            agent = self.agents.get(voter.id)
            candidates = [p.name for p in self.state.alive_players if p.id != voter.id]

            if agent and not self.use_mock:
                tgt_name, reason = agent.vote(self.state)
            else:
                tgt_name = random.choice(candidates) if candidates else ""

            tgt = self.state.get_player_by_name(tgt_name)
            if not tgt or not tgt.alive:
                tgt_name = candidates[0] if candidates else ""
                tgt = self.state.get_player_by_name(tgt_name)

            if tgt:
                self._vote_counts[tgt.id] = self._vote_counts.get(tgt.id, 0) + 1
                self.bus.publish(Event(
                    EventType.VOTE_CAST,
                    {"voter_id": voter.id, "voter_name": voter.name,
                     "target_id": tgt.id, "target_name": tgt.name},
                ))

        eliminated = self._resolve_vote()
        if eliminated:
            self.state.eliminate(eliminated.id, "voted_out")
            self.bus.publish(Event(
                EventType.PLAYER_ELIMINATED,
                {"player_id": eliminated.id, "player_name": eliminated.name,
                 "role": eliminated.role, "reason": "voted_out"},
            ))

    def _resolve_vote(self) -> object | None:
        if not self._vote_counts:
            return None
        max_votes = max(self._vote_counts.values())
        top = [pid for pid, cnt in self._vote_counts.items() if cnt == max_votes]
        target_id = top[0] if len(top) == 1 else random.choice(top)
        self.bus.publish(Event(
            EventType.VOTE_RESULT, {
                "vote_counts": {str(k): v for k, v in self._vote_counts.items()},
                "eliminated_id": target_id,
                "eliminated_name": self.state.get_player(target_id).name,
            },
        ))
        return self.state.get_player(target_id)

    def _handle_last_words(self):
        last = self.state.eliminated_history[-1] if self.state.eliminated_history else None
        if last:
            pid = last["player_id"]
            agent = self.agents.get(pid)
            text = "Good luck everyone..."
            if agent and not self.use_mock:
                text = agent.last_words(self.state)
            self.bus.publish(Event(
                EventType.PUBLIC_SPEECH,
                {"player_id": pid, "player_name": last["player_name"],
                 "content": text, "is_last_words": True},
            ))
