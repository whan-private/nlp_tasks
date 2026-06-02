"""
狼人杀游戏引擎 - 玩家模块
管理玩家创建、角色分配和信息隔离
"""

from typing import Dict, List, Optional, Any, Set
import random
import logging

from .state import GameState, PlayerState, PlayerStatus, DeathCause

logger = logging.getLogger(__name__)


class PlayerManager:
    """
    玩家管理器
    负责玩家的创建、角色分配、信息管理和状态更新
    """

    def __init__(self, game_state: GameState):
        self.game_state = game_state
        self._role_list: List[str] = []  # 角色列表
        self._player_roles: Dict[int, str] = {}  # 玩家ID -> 角色

    def create_players(self, player_names: List[str]) -> List[PlayerState]:
        """
        创建玩家

        Args:
            player_names: 玩家名称列表

        Returns:
            创建的玩家状态列表
        """
        players = []
        for idx, name in enumerate(player_names):
            player_id = idx + 1
            player = PlayerState(
                player_id=player_id,
                player_name=name,
                role_type="",  # 待分配
                position=idx + 1
            )
            players.append(player)
            self.game_state.players[player_id] = player

        self.game_state.player_order = [p.player_id for p in players]
        self.game_state.total_players = len(players)

        logger.info(f"创建了 {len(players)} 名玩家: {player_names}")
        return players

    def assign_roles(self, role_config: Dict[str, int]) -> Dict[int, str]:
        """
        分配角色

        Args:
            role_config: 角色配置，如 {"werewolf": 2, "seer": 1, "witch": 1, "hunter": 1, "villager": 1}

        Returns:
            玩家ID到角色的映射
        """
        # 构建角色列表
        role_list = []
        for role, count in role_config.items():
            role_list.extend([role] * count)

        # 随机打乱
        random.shuffle(role_list)

        # 分配给玩家
        player_ids = list(self.game_state.players.keys())
        random.shuffle(player_ids)

        for player_id, role in zip(player_ids, role_list):
            self.game_state.players[player_id].role_type = role
            self._player_roles[player_id] = role
            logger.info(f"玩家 {player_id} 获得角色: {role}")

        # 更新计数
        self.game_state.update_counts()

        return self._player_roles.copy()

    def get_player_role(self, player_id: int) -> Optional[str]:
        """获取玩家角色"""
        player = self.game_state.get_player_by_id(player_id)
        return player.role_type if player else None

    def is_werewolf(self, player_id: int) -> bool:
        """判断是否为狼人"""
        return self.get_player_role(player_id) == "werewolf"

    def is_seer(self, player_id: int) -> bool:
        """判断是否为预言家"""
        return self.get_player_role(player_id) == "seer"

    def is_witch(self, player_id: int) -> bool:
        """判断是否为女巫"""
        return self.get_player_role(player_id) == "witch"

    def is_hunter(self, player_id: int) -> bool:
        """判断是否为猎人"""
        return self.get_player_role(player_id) == "hunter"

    def is_villager(self, player_id: int) -> bool:
        """判断是否为平民"""
        return self.get_player_role(player_id) == "villager"

    def get_werewolf_team(self) -> List[int]:
        """获取狼人团队ID列表"""
        return [pid for pid, role in self._player_roles.items()
                if role == "werewolf"]

    def get_good_team(self) -> List[int]:
        """获取好人团队ID列表"""
        good_roles = ["villager", "seer", "witch", "hunter"]
        return [pid for pid, role in self._player_roles.items()
                if role in good_roles]

    def get_alive_werewolves(self) -> List[int]:
        """获取存活的狼人"""
        wolves = self.get_werewolf_team()
        return [w for w in wolves if self.game_state.players[w].is_alive()]

    def get_alive_good(self) -> List[int]:
        """获取存活的好人"""
        good = self.get_good_team()
        return [g for g in good if self.game_state.players[g].is_alive()]

    def get_private_info(self, player_id: int) -> Dict[str, Any]:
        """
        获取玩家的私有信息（信息隔离）

        每个角色只能看到与自己相关的信息

        Args:
            player_id: 玩家ID

        Returns:
            该玩家可看到的私有信息
        """
        player = self.game_state.get_player_by_id(player_id)
        if not player:
            return {}

        role = player.role_type
        private_info = {
            "role": role,
            "your_id": player_id,
            "your_name": player.player_name,
            "is_alive": player.is_alive(),
            "round": self.game_state.round_num
        }

        # 狼人信息：可以看到所有狼队友
        if role == "werewolf":
            private_info["teammates"] = self.get_werewolf_team()
            private_info["night_info"] = {
                "kill_target": self.game_state.night_info.werewolf_target if self.game_state.night_info else None
            }

        # 预言家信息：可以看到查验结果
        elif role == "seer":
            if self.game_state.night_info:
                private_info["check_result"] = {
                    "target": self.game_state.night_info.seer_target,
                    "result": self.game_state.night_info.seer_result
                }

        # 女巫信息：可以看到刀口和被救/毒信息
        elif role == "witch":
            if self.game_state.night_info:
                private_info["witch_info"] = {
                    "attacked_player": self.game_state.night_info.werewolf_target,
                    "saved_player": self.game_state.night_info.witch_save_target,
                    "poisoned_player": self.game_state.night_info.witch_poison_target,
                    "antidote_available": not player.antidote_used,
                    "poison_available": not player.poison_used
                }

        return private_info

    def get_public_info(self, player_id: int) -> Dict[str, Any]:
        """
        获取公共信息（所有玩家都能看到）

        Args:
            player_id: 玩家ID

        Returns:
            公共信息
        """
        return {
            "round": self.game_state.round_num,
            "phase": self.game_state.phase.value,
            "alive_players": self.game_state.get_alive_players(),
            "dead_players": self.game_state.get_dead_players(),
            "alive_count": self.game_state.alive_count,
            "sheriff_id": self.game_state.sheriff_id,
            "current_speaker": self.game_state.current_speaker,
            "vote_info": self._get_vote_info_public(),
            "death_info": self._get_death_info_public()
        }

    def _get_vote_info_public(self) -> Dict:
        """获取可公开的投票信息"""
        if self.game_state.vote_info:
            return {
                "eliminated": self.game_state.vote_info.eliminated_player,
                "is_tie": self.game_state.vote_info.is_tie
            }
        return {}

    def _get_death_info_public(self) -> List[Dict]:
        """获取可公开的死亡信息"""
        deaths = []
        for player_id, player in self.game_state.players.items():
            if not player.is_alive() and player.death_round == self.game_state.round_num:
                # 不公开具体死因
                deaths.append({
                    "player_id": player_id,
                    "player_name": player.player_name,
                    "death_round": player.death_round
                })
        return deaths

    def get_speech_order(self, start_from: Optional[int] = None) -> List[int]:
        """
        获取发言顺序

        Args:
            start_from: 从哪个玩家开始

        Returns:
            发言顺序列表
        """
        alive = self.game_state.get_alive_players()

        if start_from is None:
            # 默认随机顺序
            random.shuffle(alive)
            return alive

        # 从指定玩家开始
        idx = alive.index(start_from) if start_from in alive else 0
        return alive[idx:] + alive[:idx]

    def apply_death(self, player_id: int, cause: DeathCause):
        """应用玩家死亡"""
        player = self.game_state.get_player_by_id(player_id)
        if player and player.is_alive():
            player.kill(self.game_state.round_num, cause)
            logger.info(f"玩家 {player_id} 死亡，原因: {cause.value}")

    def apply_hunter_shot(self, hunter_id: int, target_id: int) -> bool:
        """
        应用猎人开枪

        Args:
            hunter_id: 猎人ID
            target_id: 目标ID

        Returns:
            是否成功
        """
        hunter = self.game_state.get_player_by_id(hunter_id)
        target = self.game_state.get_player_by_id(target_id)

        if not hunter or not target:
            return False

        if hunter.role_type != "hunter":
            logger.warning(f"{hunter_id} 不是猎人，无法开枪")
            return False

        if hunter.has_shot:
            logger.warning(f"猎人 {hunter_id} 已经开过枪")
            return False

        if target.is_alive():
            target.kill(self.game_state.round_num, DeathCause.HUNTER_SHOT)
            hunter.has_shot = True
            logger.info(f"猎人 {hunter_id} 开枪带走 {target_id}")
            return True

        return False

    def reset_all_players(self):
        """重置所有玩家状态（新游戏）"""
        for player in self.game_state.players.values():
            player.status = PlayerStatus.ALIVE
            player.death_round = 0
            player.death_cause = DeathCause.NONE
            player.has_shot = False
            player.antidote_used = False
            player.poison_used = False
            player.has_claimed = False
            player.vote_target = None
            player.vote_history = []
            player.speeches = []

        self.game_state.update_counts()
        logger.info("所有玩家状态已重置")