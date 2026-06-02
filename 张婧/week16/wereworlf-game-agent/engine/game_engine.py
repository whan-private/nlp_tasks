"""
狼人杀游戏引擎 - 主模块
整合所有模块，提供完整的游戏控制流程
"""

from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import uuid
import logging

from .state import (
    GameState, GamePhase, NightInfo, VoteInfo, DeathCause,
    PlayerState, PlayerStatus
)
from .phase import PhaseManager
from .player import PlayerManager

logger = logging.getLogger(__name__)


class GameEngine:
    """
    狼人杀游戏引擎
    负责整个游戏的控制流程、事件调度和结果记录
    """

    def __init__(self, role_config: Dict[str, int] = None):
        """
        初始化游戏引擎

        Args:
            role_config: 角色配置，如 {"werewolf": 2, "seer": 1, "witch": 1, "hunter": 1, "villager": 1}
        """
        self.role_config = role_config or {
            "werewolf": 2,
            "seer": 1,
            "witch": 1,
            "hunter": 1,
            "villager": 1
        }

        # 创建游戏状态
        self.game_state = GameState(
            game_id=str(uuid.uuid4())[:8],
            round_num=0
        )

        # 初始化管理器
        self.player_manager = PlayerManager(self.game_state)
        self.phase_manager = PhaseManager(self.game_state)

        # 事件回调
        self._event_callbacks: Dict[str, List[Callable]] = {
            "on_phase_start": [],
            "on_phase_end": [],
            "on_player_death": [],
            "on_vote": [],
            "on_game_end": []
        }

        # 行动收集器（用于AI决策）
        self.pending_actions: Dict[str, Any] = {
            "werewolf": None,
            "seer": None,
            "witch": None,
            "speeches": {},
            "votes": {}
        }

        self.is_running = False
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

    # ============ 事件系统 ============

    def register_callback(self, event: str, callback: Callable):
        """注册事件回调"""
        if event in self._event_callbacks:
            self._event_callbacks[event].append(callback)

    def _trigger_event(self, event: str, *args, **kwargs):
        """触发事件"""
        for callback in self._event_callbacks.get(event, []):
            try:
                callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"事件回调执行失败: {e}")

    # ============ 游戏初始化 ============

    def init_game(self, player_names: List[str]) -> bool:
        """
        初始化游戏

        Args:
            player_names: 玩家名称列表

        Returns:
            是否成功
        """
        total_players = len(player_names)
        total_roles = sum(self.role_config.values())

        if total_players != total_roles:
            logger.error(f"玩家数量({total_players})与角色数量({total_roles})不匹配")
            return False

        # 创建玩家
        self.player_manager.create_players(player_names)

        # 分配角色
        self.player_manager.assign_roles(self.role_config)

        # 重置状态
        self.game_state.round_num = 0
        self.game_state.night_history = []
        self.game_state.vote_history = []

        self.start_time = datetime.now()
        self.is_running = True

        logger.info(f"游戏初始化完成，玩家: {player_names}")
        logger.info(f"角色配置: {self.role_config}")

        return True

    # ============ 游戏流程控制 ============

    def start_game(self) -> Dict[str, Any]:
        """
        开始游戏

        Returns:
            游戏结果
        """
        if not self.is_running:
            logger.error("游戏未初始化")
            return {"success": False, "error": "游戏未初始化"}

        logger.info("========== 游戏开始 ==========")

        # 进入第一轮
        self.game_state.next_round()

        # 主游戏循环
        while not self.game_state.is_game_over:
            try:
                round_result = self._run_round()
                logger.info(f"第{self.game_state.round_num}轮结束: {round_result}")

                # 检查游戏结束
                is_over, winner = self.game_state.check_game_over()
                if is_over:
                    break

            except Exception as e:
                logger.error(f"游戏循环出错: {e}")
                break

        # 游戏结束
        self.end_time = datetime.now()
        self.is_running = False

        result = self._get_game_result()
        self._trigger_event("on_game_end", result)

        logger.info(f"========== 游戏结束，获胜方: {result['winner']} ==========")

        return result

    def _run_round(self) -> Dict[str, Any]:
        """
        运行一轮游戏

        Returns:
            本轮结果
        """
        logger.info(f"\n========== 第 {self.game_state.round_num} 轮 ==========")

        # 收集各阶段行动
        actions = self._collect_round_actions()

        # 执行完整的一轮
        results = self.phase_manager.run_full_round(actions)

        # 处理猎人开枪（如果有）
        if results.get("settlement", {}).get("hunter_triggered"):
            self._handle_hunter_shot()

        # 更新游戏状态
        self.game_state.update_counts()

        return results

    def _collect_round_actions(self) -> Dict[str, Any]:
        """
        收集本轮所有行动

        实际使用时，这里会调用Agent的决策接口

        Returns:
            收集到的行动
        """
        # 这里返回的是占位数据，实际使用时需要从Agent获取
        return {
            "werewolf": self.pending_actions.get("werewolf", {"target": None}),
            "seer": self.pending_actions.get("seer", {"target": None}),
            "witch": self.pending_actions.get("witch", {"save": None, "poison": None}),
            "speeches": self.pending_actions.get("speeches", {}),
            "votes": self.pending_actions.get("votes", {})
        }

    def _handle_hunter_shot(self):
        """处理猎人开枪"""
        # 获取被放逐的玩家
        eliminated = None
        if self.game_state.vote_info:
            eliminated = self.game_state.vote_info.eliminated_player

        if eliminated:
            player = self.game_state.get_player_by_id(eliminated)
            if player and player.role_type == "hunter" and not player.has_shot:
                # 需要从外部获取猎人开枪目标
                # 这里预留接口
                logger.info(f"猎人 {eliminated} 被放逐，等待开枪决策")

    def _get_game_result(self) -> Dict[str, Any]:
        """获取游戏结果"""
        return {
            "game_id": self.game_state.game_id,
            "winner": self.game_state.winner,
            "total_rounds": self.game_state.round_num,
            "duration_seconds": (self.end_time - self.start_time).total_seconds() if self.end_time else 0,
            "final_state": self.game_state.to_dict(),
            "players": [
                {
                    "id": p.player_id,
                    "name": p.player_name,
                    "role": p.role_type,
                    "survived": p.is_alive(),
                    "death_round": p.death_round,
                    "death_cause": p.death_cause.value if p.death_cause else None
                }
                for p in self.game_state.players.values()
            ]
        }

    # ============ Agent交互接口 ============

    def submit_werewolf_action(self, target_id: Optional[int],
                               attackers: List[int] = None) -> bool:
        """
        提交狼人行动

        Args:
            target_id: 刀人目标
            attackers: 参与刀人的狼人ID

        Returns:
            是否成功
        """
        self.pending_actions["werewolf"] = {
            "target": target_id,
            "attackers": attackers or []
        }
        return True

    def submit_seer_action(self, target_id: Optional[int]) -> bool:
        """
        提交预言家行动

        Args:
            target_id: 查验目标

        Returns:
            是否成功
        """
        self.pending_actions["seer"] = {"target": target_id}
        return True

    def submit_witch_action(self, save_target: Optional[int] = None,
                            poison_target: Optional[int] = None) -> bool:
        """
        提交女巫行动

        Args:
            save_target: 救人目标
            poison_target: 毒人目标

        Returns:
            是否成功
        """
        self.pending_actions["witch"] = {
            "save": save_target,
            "poison": poison_target
        }
        return True

    def submit_speech(self, player_id: int, content: str) -> bool:
        """
        提交玩家发言

        Args:
            player_id: 发言玩家
            content: 发言内容

        Returns:
            是否成功
        """
        self.pending_actions["speeches"][player_id] = content
        return True

    def submit_vote(self, voter_id: int, target_id: int) -> bool:
        """
        提交投票

        Args:
            voter_id: 投票者
            target_id: 投票目标

        Returns:
            是否成功
        """
        self.pending_actions["votes"][voter_id] = target_id
        return True

    def reset_pending_actions(self):
        """重置待处理行动"""
        self.pending_actions = {
            "werewolf": None,
            "seer": None,
            "witch": None,
            "speeches": {},
            "votes": {}
        }

    # ============ 查询接口 ============

    def get_game_state(self) -> GameState:
        """获取游戏状态"""
        return self.game_state

    def get_player_state(self, player_id: int) -> Optional[PlayerState]:
        """获取玩家状态"""
        return self.game_state.get_player_by_id(player_id)

    def get_public_info(self, player_id: int) -> Dict:
        """获取公共信息"""
        return self.player_manager.get_public_info(player_id)

    def get_private_info(self, player_id: int) -> Dict:
        """获取私有信息"""
        return self.player_manager.get_private_info(player_id)

    def get_speech_order(self, player_id: int) -> List[int]:
        """获取发言顺序"""
        return self.player_manager.get_speech_order()

    def is_game_over(self) -> bool:
        """游戏是否结束"""
        return self.game_state.is_game_over

    def get_winner(self) -> Optional[str]:
        """获取获胜方"""
        return self.game_state.winner


# ============ 使用示例 ============

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.INFO)

    # 创建游戏引擎
    engine = GameEngine(role_config={
        "werewolf": 2,
        "seer": 1,
        "witch": 1,
        "hunter": 1,
        "villager": 1
    })

    # 初始化游戏
    players = ["玩家1", "玩家2", "玩家3", "玩家4", "玩家5", "玩家6"]
    engine.init_game(players)

    # 模拟行动提交
    engine.submit_werewolf_action(target_id=3)
    engine.submit_seer_action(target_id=5)
    engine.submit_witch_action(save_target=3, poison_target=None)

    # 模拟发言和投票
    for pid in range(1, 7):
        engine.submit_speech(pid, f"我是{pid}号，我是好人")
        engine.submit_vote(pid, 3 if pid % 2 == 0 else 4)

    # 开始游戏
    result = engine.start_game()
    print(f"\n游戏结果: {result}")