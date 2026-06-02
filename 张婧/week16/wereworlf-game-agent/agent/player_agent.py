"""
狼人杀多智能体系统 - 玩家角色Agent模块
实现各角色的具体Agent类
"""

from typing import Optional, List, Dict, Any, Tuple
import random
import re

from base_agent import (
    BaseAgent, RoleType, GameConfig, GameState, NightInfo,
    Action, ActionType, GamePhase
)
import logging

logger = logging.getLogger(__name__)


class VillagerAgent(BaseAgent):
    """
    平民Agent

    平民没有特殊技能，依靠逻辑推理和发言帮助好人阵营获胜
    """

    def __init__(
            self,
            player_id: int,
            player_name: str,
            game_config: GameConfig = None,
            is_conservative: bool = True
    ):
        super().__init__(player_id, player_name, RoleType.VILLAGER, game_config)
        self.is_conservative = is_conservative
        self.has_voted_today = False

    def perceive(self, game_state: GameState, private_info: Dict) -> None:
        """感知环境状态"""
        self.update_state(game_state)
        # 平民没有私有信息

    def decide_speech(self, round_num: int, position: str) -> str:
        """决定发言内容"""
        if round_num == 1:
            return self._first_round_speech()
        else:
            return self._analysis_speech()

    def _first_round_speech(self) -> str:
        """第一轮发言"""
        if self.is_conservative:
            speeches = [
                "我是好人，过。",
                "平民一个，没啥信息，过。",
                "好人，听预言家怎么说。"
            ]
            return random.choice(speeches)
        else:
            return "我是好人，这一轮我会仔细听大家的发言，找出狼人的破绽。过。"

    def _analysis_speech(self) -> str:
        """分析发言"""
        parts = ["我是好人。"]

        # 表达怀疑
        suspected = self.get_most_suspected()
        if suspected:
            parts.append(f"我觉得{suspected}号玩家行为可疑，")

        # 表达信任
        trusted = self.get_most_trusted()
        if trusted:
            parts.append(f"我比较相信{trusted}号。")

        # 投票意向
        target = self.decide_vote(self.round_num, self.alive_players)
        if target:
            parts.append(f"这一轮我会投票给{target}号。")

        parts.append("过。")
        return "".join(parts)

    def decide_vote(self, round_num: int, alive_players: List[int]) -> Optional[int]:
        """决定投票目标"""
        if self.has_voted_today:
            return None

        candidates = [p for p in alive_players if p != self.player_id]
        if not candidates:
            return None

        target = self.get_most_suspected()
        if target and target in candidates:
            self.has_voted_today = True
            return target

        self.has_voted_today = True
        return random.choice(candidates) if candidates else None

    def night_action(self, round_num: int, night_info: NightInfo) -> Action:
        """平民夜间无行动"""
        return Action(
            player_id=self.player_id,
            action_type=ActionType.NONE,
            round_num=round_num
        )

    def reset_for_new_game(self):
        """重置状态"""
        super().reset()
        self.has_voted_today = False


class SeerAgent(BaseAgent):
    """
    预言家Agent

    预言家可以在夜间查验玩家身份
    """

    def __init__(self, player_id: int, player_name: str, game_config: GameConfig = None):
        super().__init__(player_id, player_name, RoleType.SEER, game_config)
        self.check_history: List[Tuple[int, str]] = []  # 查验历史
        self.has_claimed = False  # 是否已起跳
        self.seer_line: List[int] = []  # 警徽流

    def perceive(self, game_state: GameState, private_info: Dict) -> None:
        """感知环境状态"""
        self.update_state(game_state)

    def decide_speech(self, round_num: int, position: str) -> str:
        """决定发言内容"""
        if not self.has_claimed and round_num == 1:
            # 第一轮起跳
            self.has_claimed = True
            return self._claim_speech()
        elif self.has_claimed:
            return self._update_speech()
        else:
            return self._hidden_speech()

    def _claim_speech(self) -> str:
        """起跳发言"""
        if not self.check_history:
            return "我是预言家，今晚会开始查验，请大家相信我。"

        last_check = self.check_history[-1]
        result_text = "金水" if last_check[1] == "good" else "查杀"

        parts = [
            "我是预言家，",
            f"昨晚查验了{last_check[0]}号玩家，",
            f"是{result_text}。",
        ]

        if self.seer_line:
            parts.append(f"警徽流: {self.seer_line}")

        parts.append("请好人玩家们投给我警徽，我会带领大家找出所有狼人。过。")
        return "".join(parts)

    def _update_speech(self) -> str:
        """更新发言"""
        parts = ["我是预言家，"]

        # 报告最新的查验结果
        if self.check_history:
            latest = self.check_history[-1]
            result_text = "金水" if latest[1] == "good" else "查杀"
            parts.append(f"昨晚查验了{latest[0]}号，是{result_text}，")

        # 指出可疑对象
        suspected = self.get_most_suspected()
        if suspected:
            parts.append(f"我怀疑{suspected}号是狼人，")

        parts.append("过。")
        return "".join(parts)

    def _hidden_speech(self) -> str:
        """隐藏身份的发言"""
        return "我是好人，过。"

    def decide_vote(self, round_num: int, alive_players: List[int]) -> Optional[int]:
        """决定投票目标"""
        candidates = [p for p in alive_players if p != self.player_id]
        if not candidates:
            return None

        # 优先投给查杀的狼人
        for target, result in self.check_history:
            if result == "wolf" and target in candidates:
                return target

        # 其次投给怀疑的人
        suspected = self.get_most_suspected()
        if suspected and suspected in candidates:
            return suspected

        return None

    def night_action(self, round_num: int, night_info: NightInfo) -> Action:
        """夜间查验"""
        # 决定查验目标
        target = self._decide_check_target()
        if target is None:
            return Action(
                player_id=self.player_id,
                action_type=ActionType.NONE,
                round_num=round_num
            )

        return Action(
            player_id=self.player_id,
            action_type=ActionType.CHECK,
            target_id=target,
            round_num=round_num
        )

    def _decide_check_target(self) -> Optional[int]:
        """决定查验目标"""
        # 过滤已查验过的玩家
        checked = {t[0] for t in self.check_history}
        candidates = [p for p in self.alive_players if p not in checked and p != self.player_id]

        if not candidates:
            return None

        # 优先查验可疑玩家
        suspected = self.get_most_suspected()
        if suspected and suspected in candidates:
            return suspected

        return random.choice(candidates) if candidates else None

    def record_check_result(self, target_id: int, result: str):
        """记录查验结果"""
        self.check_history.append((target_id, result))
        if result == "wolf":
            self.suspicion_scores[target_id] = 1.0
            self.trust_scores[target_id] = 0.0
        else:
            self.trust_scores[target_id] = 1.0
            self.suspicion_scores[target_id] = 0.0

    def set_seer_line(self, first: int, second: Optional[int] = None):
        """设置警徽流"""
        self.seer_line = [first]
        if second:
            self.seer_line.append(second)

    def reset_for_new_game(self):
        """重置状态"""
        super().reset()
        self.check_history = []
        self.has_claimed = False
        self.seer_line = []


class WitchAgent(BaseAgent):
    """
    女巫Agent

    女巫拥有解药和毒药，可以救人或毒人
    """

    def __init__(self, player_id: int, player_name: str, game_config: GameConfig = None):
        super().__init__(player_id, player_name, RoleType.WITCH, game_config)
        self.has_antidote = True  # 解药
        self.has_poison = True  # 毒药
        self.antidote_used = False
        self.poison_used = False
        self.last_night_attack_target: Optional[int] = None

    def perceive(self, game_state: GameState, private_info: Dict) -> None:
        """感知环境状态"""
        self.update_state(game_state)

        # 接收夜间信息
        if "attacked_player" in private_info:
            self.last_night_attack_target = private_info["attacked_player"]

    def decide_speech(self, round_num: int, position: str) -> str:
        """决定发言内容"""
        if self.has_antidote or self.has_poison:
            # 有药时低调
            return self._hidden_speech()
        else:
            # 没药时可以适当暴露
            return self._exposed_speech()

    def _hidden_speech(self) -> str:
        """隐藏身份的发言"""
        return "我是好人，过。"

    def _exposed_speech(self) -> str:
        """暴露身份的发言"""
        parts = ["我是女巫，药已经用完了，"]

        suspected = self.get_most_suspected()
        if suspected:
            parts.append(f"我怀疑{suspected}号是狼人，")

        parts.append("过。")
        return "".join(parts)

    def decide_vote(self, round_num: int, alive_players: List[int]) -> Optional[int]:
        """决定投票目标"""
        candidates = [p for p in alive_players if p != self.player_id]
        if not candidates:
            return None

        suspected = self.get_most_suspected()
        if suspected and suspected in candidates:
            return suspected

        return None

    def night_action(self, round_num: int, night_info: NightInfo) -> Action:
        """夜间行动"""
        # 如果没有被袭击的人，直接跳过
        if night_info.attacked_player_id is None:
            return Action(
                player_id=self.player_id,
                action_type=ActionType.NONE,
                round_num=round_num
            )

        # 决定是否使用解药
        if self.has_antidote and not self.antidote_used:
            # 判断是否自救（根据规则）
            if night_info.attacked_player_id == self.player_id:
                if not self.game_config.witch_can_save_self:
                    pass  # 不能自救
                else:
                    self.antidote_used = True
                    self.has_antidote = False
                    return Action(
                        player_id=self.player_id,
                        action_type=ActionType.SAVE,
                        target_id=night_info.attacked_player_id,
                        round_num=round_num
                    )
            else:
                # 救别人
                self.antidote_used = True
                self.has_antidote = False
                return Action(
                    player_id=self.player_id,
                    action_type=ActionType.SAVE,
                    target_id=night_info.attacked_player_id,
                    round_num=round_num
                )

        return Action(
            player_id=self.player_id,
            action_type=ActionType.NONE,
            round_num=round_num
        )

    def use_poison(self, target_id: int, round_num: int) -> Action:
        """使用毒药"""
        if self.has_poison and not self.poison_used:
            self.poison_used = True
            self.has_poison = False
            return Action(
                player_id=self.player_id,
                action_type=ActionType.POISON,
                target_id=target_id,
                round_num=round_num
            )
        return Action(
            player_id=self.player_id,
            action_type=ActionType.NONE,
            round_num=round_num
        )

    def reset_for_new_game(self):
        """重置状态"""
        super().reset()
        self.has_antidote = True
        self.has_poison = True
        self.antidote_used = False
        self.poison_used = False
        self.last_night_attack_target = None


class HunterAgent(BaseAgent):
    """
    猎人Agent

    猎人死亡时可以开枪带走一名玩家
    """

    def __init__(self, player_id: int, player_name: str, game_config: GameConfig = None):
        super().__init__(player_id, player_name, RoleType.HUNTER, game_config)
        self.has_shot = False
        self.is_hidden = True
        self.death_cause: Optional[str] = None

    def perceive(self, game_state: GameState, private_info: Dict) -> None:
        """感知环境状态"""
        self.update_state(game_state)

    def decide_speech(self, round_num: int, position: str) -> str:
        """决定发言内容"""
        if self.is_hidden:
            return self._hidden_speech()
        else:
            return self._exposed_speech()

    def _hidden_speech(self) -> str:
        """隐藏身份的发言"""
        return "我是好人，过。"

    def _exposed_speech(self) -> str:
        """暴露身份的发言"""
        parts = ["我是猎人，"]

        suspected = self.get_most_suspected()
        if suspected:
            parts.append(f"我觉得{suspected}号是狼人，")

        parts.append("谁要是敢票我，我就带谁走。过。")
        return "".join(parts)

    def decide_vote(self, round_num: int, alive_players: List[int]) -> Optional[int]:
        """决定投票目标"""
        candidates = [p for p in alive_players if p != self.player_id]
        if not candidates:
            return None

        suspected = self.get_most_suspected()
        if suspected and suspected in candidates:
            return suspected

        return None

    def night_action(self, round_num: int, night_info: NightInfo) -> Action:
        """猎人夜间无行动"""
        return Action(
            player_id=self.player_id,
            action_type=ActionType.NONE,
            round_num=round_num
        )

    def on_death(self, death_cause: str, round_num: int, alive_players: List[int]) -> Optional[Action]:
        """
        死亡时触发，决定是否开枪

        Args:
            death_cause: 死亡原因
            round_num: 当前轮次
            alive_players: 存活的玩家列表

        Returns:
            开枪Action，如果不开枪则返回None
        """
        self.death_cause = death_cause

        # 被毒死不能开枪
        if death_cause == "witch_poison":
            logger.info(f"猎人 {self.player_name} 被毒死，无法开枪")
            return None

        # 已经开过枪不能再次开枪
        if self.has_shot:
            return None

        # 决定是否开枪
        target = self._decide_shoot_target(alive_players)
        if target is None:
            return None

        self.has_shot = True
        return Action(
            player_id=self.player_id,
            action_type=ActionType.SHOOT,
            target_id=target,
            round_num=round_num
        )

    def _decide_shoot_target(self, alive_players: List[int]) -> Optional[int]:
        """决定开枪目标"""
        candidates = [p for p in alive_players if p != self.player_id]
        if not candidates:
            return None

        # 优先带走确认的狼人
        for pid, score in self.suspicion_scores.items():
            if score > 0.8 and pid in candidates:
                return pid

        # 其次带走怀疑度最高的
        suspected = self.get_most_suspected()
        if suspected and suspected in candidates:
            return suspected

        return None

    def reveal_identity(self):
        """暴露猎人身份"""
        self.is_hidden = False

    def reset_for_new_game(self):
        """重置状态"""
        super().reset()
        self.has_shot = False
        self.is_hidden = True
        self.death_cause = None


class WerewolfAgent(BaseAgent):
    """
    狼人Agent

    狼人可以在夜间刀人，白天伪装身份
    """

    def __init__(self, player_id: int, player_name: str, game_config: GameConfig = None):
        super().__init__(player_id, player_name, RoleType.WEREWOLF, game_config)
        self.teammates: List[int] = []  # 狼队友ID
        self.has_killed = False
        self.strategy = "deep_water"  # deep_water, hard_jump, witch_hunt
        self.fake_checks: Dict[int, str] = {}  # 伪造的查验结果

    def set_teammates(self, teammates: List[int]):
        """设置狼队友"""
        self.teammates = teammates

    def perceive(self, game_state: GameState, private_info: Dict) -> None:
        """感知环境状态"""
        self.update_state(game_state)

        # 接收夜间信息（谁被刀了）
        if "kill_target" in private_info:
            pass  # 记录刀人信息

    def decide_speech(self, round_num: int, position: str) -> str:
        """根据策略决定发言"""
        if self.strategy == "hard_jump":
            return self._hard_jump_speech()
        elif self.strategy == "witch_hunt":
            return self._witch_hunt_speech()
        else:  # deep_water
            return self._deep_water_speech()

    def _deep_water_speech(self) -> str:
        """深水狼发言（伪装平民）"""
        speeches = [
            "我是好人，过。",
            "平民一个，听预言家的。",
            "我是村民，没什么信息。",
            "好人，跟警长投票。"
        ]
        return random.choice(speeches)

    def _hard_jump_speech(self) -> str:
        """悍跳狼发言（冒充预言家）"""
        if not self.fake_checks:
            # 随机生成假查验
            target = random.choice([p for p in self.alive_players if p != self.player_id])
            result = random.choice(["金水", "查杀"])
            self.fake_checks[target] = "good" if result == "金水" else "wolf"

        last_target = list(self.fake_checks.keys())[-1]
        last_result = "金水" if self.fake_checks[last_target] == "good" else "查杀"

        return f"我是预言家，昨晚查验了{last_target}号玩家，是{last_result}。请好人玩家们投给我警徽。过。"

    def _witch_hunt_speech(self) -> str:
        """倒钩狼发言（站边真预言家）"""
        # 找到真预言家（假设）
        real_seer = None
        for pid in self.alive_players:
            if pid in self.trust_scores and self.trust_scores[pid] > 0.7:
                real_seer = pid
                break

        if real_seer:
            return f"我相信{real_seer}号是预言家，他的发言逻辑清晰，我会跟着他投票。过。"
        return self._deep_water_speech()

    def decide_vote(self, round_num: int, alive_players: List[int]) -> Optional[int]:
        """决定投票目标"""
        candidates = [p for p in alive_players if p != self.player_id]
        if not candidates:
            return None

        # 狼队协作：投给约定目标（需要外部协调）
        # 这里简化处理：投给非队友中嫌疑最大的
        non_teammates = [p for p in candidates if p not in self.teammates]
        if non_teammates:
            # 投给信任度最低的
            min_trust = min(non_teammates, key=lambda x: self.trust_scores.get(x, 0.5))
            return min_trust

        return random.choice(candidates) if candidates else None

    def night_action(self, round_num: int, night_info: NightInfo) -> Action:
        """夜间刀人"""
        if self.has_killed:
            return Action(
                player_id=self.player_id,
                action_type=ActionType.NONE,
                round_num=round_num
            )

        # 决定刀人目标（不刀队友）
        candidates = [p for p in self.alive_players if p not in self.teammates and p != self.player_id]
        if not candidates:
            return Action(
                player_id=self.player_id,
                action_type=ActionType.NONE,
                round_num=round_num
            )

        # 选择目标
        target = self._decide_kill_target(candidates)

        return Action(
            player_id=self.player_id,
            action_type=ActionType.KILL,
            target_id=target,
            round_num=round_num
        )

    def _decide_kill_target(self, candidates: List[int]) -> int:
        """决定刀人目标"""
        # 优先刀疑似预言家的
        for pid in candidates:
            if pid in self.trust_scores and self.trust_scores[pid] > 0.8:
                return pid

        # 其次随机选择
        return random.choice(candidates) if candidates else candidates[0]

    def set_strategy(self, strategy: str):
        """设置策略"""
        self.strategy = strategy

    def set_fake_check(self, target: int, result: str):
        """设置假查验"""
        self.fake_checks[target] = result

    def reset_for_new_game(self):
        """重置状态"""
        super().reset()
        self.teammates = []
        self.has_killed = False
        self.strategy = "deep_water"
        self.fake_checks = {}