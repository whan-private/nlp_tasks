"""
狼人杀游戏引擎 - 阶段模块
管理游戏各阶段的流转和逻辑
"""

from typing import Dict, List, Optional, Tuple, Callable, Any
from enum import Enum
import logging

from .state import (
    GameState, GamePhase, NightInfo, VoteInfo, DeathCause,
    PlayerState, PlayerStatus
)

logger = logging.getLogger(__name__)


class PhaseManager:
    """
    阶段管理器
    负责管理游戏各阶段的流转和执行
    """

    def __init__(self, game_state: GameState):
        self.game_state = game_state
        self.phase_handlers: Dict[GamePhase, Callable] = {}
        self._register_handlers()

    def _register_handlers(self):
        """注册阶段处理器"""
        self.phase_handlers[GamePhase.NIGHT_WEREWOLF] = self._handle_werewolf_phase
        self.phase_handlers[GamePhase.NIGHT_SEER] = self._handle_seer_phase
        self.phase_handlers[GamePhase.NIGHT_WITCH] = self._handle_witch_phase
        self.phase_handlers[GamePhase.DAY_DISCUSSION] = self._handle_discussion_phase
        self.phase_handlers[GamePhase.DAY_VOTING] = self._handle_voting_phase
        self.phase_handlers[GamePhase.DAY_SETTLEMENT] = self._handle_settlement_phase

    def set_phase(self, phase: GamePhase):
        """设置当前阶段"""
        self.game_state.phase = phase
        logger.info(f"游戏进入阶段: {phase.value}")

    def next_phase(self) -> GamePhase:
        """切换到下一阶段"""
        current = self.game_state.phase

        # 夜间阶段流转
        if current == GamePhase.NIGHT:
            return GamePhase.NIGHT_WEREWOLF
        elif current == GamePhase.NIGHT_WEREWOLF:
            return GamePhase.NIGHT_SEER
        elif current == GamePhase.NIGHT_SEER:
            return GamePhase.NIGHT_WITCH
        elif current == GamePhase.NIGHT_WITCH:
            return GamePhase.DAY_DISCUSSION

        # 白天阶段流转
        elif current == GamePhase.DAY_DISCUSSION:
            return GamePhase.DAY_VOTING
        elif current == GamePhase.DAY_VOTING:
            return GamePhase.DAY_SETTLEMENT
        elif current == GamePhase.DAY_SETTLEMENT:
            # 检查游戏是否结束
            is_over, winner = self.game_state.check_game_over()
            if is_over:
                return GamePhase.GAME_OVER
            else:
                self.game_state.next_round()
                return GamePhase.NIGHT

        return current

    def execute_phase(self, phase: GamePhase, **kwargs) -> Dict[str, Any]:
        """
        执行指定阶段

        Args:
            phase: 要执行的阶段
            **kwargs: 阶段需要的参数（如玩家行动结果）

        Returns:
            阶段执行结果
        """
        handler = self.phase_handlers.get(phase)
        if handler:
            return handler(**kwargs)
        else:
            logger.warning(f"未找到阶段处理器: {phase}")
            return {"success": False, "message": f"未找到阶段处理器: {phase}"}

    # ============ 阶段处理器 ============

    def _handle_werewolf_phase(self, kill_target: Optional[int] = None,
                               attackers: List[int] = None) -> Dict:
        """
        处理狼人刀人阶段

        Args:
            kill_target: 狼人选择的刀人目标
            attackers: 参与刀人的狼人ID列表

        Returns:
            执行结果
        """
        night_info = self.game_state.night_info

        if kill_target is not None:
            night_info.werewolf_target = kill_target
            night_info.werewolf_attackers = attackers or []
            logger.info(f"狼人选择刀 {kill_target} 号玩家")

            return {
                "success": True,
                "target": kill_target,
                "message": f"狼人选择刀 {kill_target} 号"
            }
        else:
            # 空刀
            logger.info("狼人选择空刀")
            return {
                "success": True,
                "target": None,
                "message": "狼人选择空刀"
            }

    def _handle_seer_phase(self, check_target: Optional[int] = None,
                           check_result: Optional[str] = None) -> Dict:
        """
        处理预言家查验阶段

        Args:
            check_target: 预言家查验的目标
            check_result: 查验结果 ('good' or 'werewolf')

        Returns:
            执行结果
        """
        night_info = self.game_state.night_info

        if check_target is not None:
            night_info.seer_target = check_target
            night_info.seer_result = check_result
            logger.info(f"预言家查验 {check_target} 号，结果: {check_result}")

            return {
                "success": True,
                "target": check_target,
                "result": check_result,
                "message": f"查验 {check_target} 号，结果是 {check_result}"
            }

        return {
            "success": True,
            "target": None,
            "message": "预言家未行动"
        }

    def _handle_witch_phase(self, save_target: Optional[int] = None,
                            poison_target: Optional[int] = None) -> Dict:
        """
        处理女巫行动阶段

        Args:
            save_target: 女巫救人的目标
            poison_target: 女巫毒人的目标

        Returns:
            执行结果
        """
        night_info = self.game_state.night_info

        # 处理救人
        if save_target is not None:
            night_info.witch_save_target = save_target
            night_info.antidote_used = True
            logger.info(f"女巫使用解药救 {save_target} 号")

        # 处理毒人
        if poison_target is not None:
            night_info.witch_poison_target = poison_target
            night_info.poison_used = True
            logger.info(f"女巫使用毒药毒 {poison_target} 号")

        # 结算死亡
        final_deaths = self._settle_night_deaths()
        night_info.final_deaths = final_deaths

        return {
            "success": True,
            "saved": save_target,
            "poisoned": poison_target,
            "deaths": final_deaths,
            "message": f"女巫行动完成，死亡: {final_deaths}"
        }

    def _settle_night_deaths(self) -> List[int]:
        """
        结算夜间死亡

        规则：
        1. 被刀的人如果被救，则不死
        2. 被毒的人必死
        3. 同一个人被刀和毒，算毒死（不能救）
        """
        night_info = self.game_state.night_info
        deaths = []

        # 处理被毒的人
        poison_target = night_info.witch_poison_target
        if poison_target is not None:
            deaths.append(poison_target)
            night_info.death_causes[poison_target] = DeathCause.WITCH_POISON

        # 处理被刀的人
        kill_target = night_info.werewolf_target
        if kill_target is not None:
            # 如果被刀的人不是被毒的人
            if kill_target != poison_target:
                # 检查是否被救
                if night_info.witch_save_target != kill_target:
                    deaths.append(kill_target)
                    night_info.death_causes[kill_target] = DeathCause.WEREWOLF_KILL
                else:
                    logger.info(f"{kill_target} 号被狼刀但被女巫救下")

        # 应用死亡
        for player_id in deaths:
            player = self.game_state.get_player_by_id(player_id)
            if player:
                player.kill(self.game_state.round_num, night_info.death_causes[player_id])

        return deaths

    def _handle_discussion_phase(self, speeches: Dict[int, str] = None) -> Dict:
        """
        处理白天讨论阶段

        Args:
            speeches: 玩家发言字典 {player_id: speech_content}

        Returns:
            执行结果
        """
        if speeches:
            for player_id, speech in speeches.items():
                player = self.game_state.get_player_by_id(player_id)
                if player and player.is_alive():
                    player.speeches.append(speech)
                    logger.debug(f"{player_id}号发言: {speech[:50]}...")

        return {
            "success": True,
            "speech_count": len(speeches) if speeches else 0,
            "message": "讨论阶段完成"
        }

    def _handle_voting_phase(self, votes: Dict[int, int] = None) -> Dict:
        """
        处理投票阶段

        Args:
            votes: 投票字典 {voter_id: target_id}

        Returns:
            执行结果
        """
        vote_info = VoteInfo(round_num=self.game_state.round_num)

        if votes:
            for voter_id, target_id in votes.items():
                # 验证投票合法性
                voter = self.game_state.get_player_by_id(voter_id)
                if voter and voter.is_alive():
                    vote_info.add_vote(voter_id, target_id)
                    voter.vote_target = target_id
                    voter.vote_history.append(target_id)

        # 计算被放逐的玩家
        eliminated = vote_info.get_eliminated()

        # 平局处理
        if vote_info.is_tie:
            # 简单处理：平局无人出局
            eliminated = None
            logger.info("投票出现平局，无人被放逐")

        self.game_state.vote_info = vote_info
        self.game_state.vote_history.append(vote_info)

        return {
            "success": True,
            "votes": votes,
            "eliminated": eliminated,
            "is_tie": vote_info.is_tie,
            "message": f"投票完成，{'平局' if vote_info.is_tie else f'{eliminated}号被放逐'}"
        }

    def _handle_settlement_phase(self) -> Dict:
        """
        处理白天结算阶段（执行放逐）

        Returns:
            执行结果
        """
        eliminated = None
        if self.game_state.vote_info:
            eliminated = self.game_state.vote_info.eliminated_player

        if eliminated is not None:
            player = self.game_state.get_player_by_id(eliminated)
            if player and player.is_alive():
                player.kill(self.game_state.round_num, DeathCause.VOTE_OUT)
                logger.info(f"{eliminated} 号玩家被投票放逐")

                # 触发猎人开枪（如果猎人被放逐）
                if player.role_type == "hunter" and not player.has_shot:
                    # 猎人开枪逻辑在外部处理
                    return {
                        "success": True,
                        "eliminated": eliminated,
                        "hunter_triggered": True,
                        "message": f"{eliminated}号被放逐，触发猎人技能"
                    }

        return {
            "success": True,
            "eliminated": eliminated,
            "hunter_triggered": False,
            "message": f"结算完成，{'无人出局' if eliminated is None else f'{eliminated}号出局'}"
        }

    def run_full_round(self, actions: Dict[str, Any]) -> Dict[str, Any]:
        """
        运行完整的一轮游戏

        Args:
            actions: 各阶段的行动结果
                {
                    "werewolf": {"target": 3},
                    "seer": {"target": 5, "result": "good"},
                    "witch": {"save": None, "poison": 6},
                    "speeches": {1: "...", 2: "..."},
                    "votes": {1: 3, 2: 4, ...}
                }

        Returns:
            本轮结果
        """
        results = {}

        # 夜间阶段
        self.set_phase(GamePhase.NIGHT_WEREWOLF)
        results["werewolf"] = self.execute_phase(
            GamePhase.NIGHT_WEREWOLF,
            kill_target=actions.get("werewolf", {}).get("target"),
            attackers=actions.get("werewolf", {}).get("attackers")
        )

        self.set_phase(GamePhase.NIGHT_SEER)
        results["seer"] = self.execute_phase(
            GamePhase.NIGHT_SEER,
            check_target=actions.get("seer", {}).get("target"),
            check_result=actions.get("seer", {}).get("result")
        )

        self.set_phase(GamePhase.NIGHT_WITCH)
        results["witch"] = self.execute_phase(
            GamePhase.NIGHT_WITCH,
            save_target=actions.get("witch", {}).get("save"),
            poison_target=actions.get("witch", {}).get("poison")
        )

        # 保存夜间信息
        self.game_state.night_history.append(self.game_state.night_info)

        # 检查游戏是否结束
        is_over, winner = self.game_state.check_game_over()
        if is_over:
            results["game_over"] = {"winner": winner}
            return results

        # 白天阶段
        self.set_phase(GamePhase.DAY_DISCUSSION)
        results["discussion"] = self.execute_phase(
            GamePhase.DAY_DISCUSSION,
            speeches=actions.get("speeches", {})
        )

        self.set_phase(GamePhase.DAY_VOTING)
        results["voting"] = self.execute_phase(
            GamePhase.DAY_VOTING,
            votes=actions.get("votes", {})
        )

        self.set_phase(GamePhase.DAY_SETTLEMENT)
        results["settlement"] = self.execute_phase(GamePhase.DAY_SETTLEMENT)

        # 再次检查游戏结束
        is_over, winner = self.game_state.check_game_over()
        if is_over:
            results["game_over"] = {"winner": winner}

        return results