"""
狼人杀多智能体系统 - 总结与复盘模块
提供游戏数据收集、统计分析和复盘报告生成功能
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import json
import logging

from base_agent import (
    Action, ActionType, VoteResult, GameState, GamePhase,
    RoleType, PlayerInfo, GameConfig
)

logger = logging.getLogger(__name__)


@dataclass
class RoundSummary:
    """单轮游戏总结"""
    round_num: int
    night_actions: List[Action] = field(default_factory=list)
    day_speeches: List[Dict] = field(default_factory=list)
    vote_result: Optional[VoteResult] = None
    eliminated_player: Optional[int] = None
    death_cause: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "round": self.round_num,
            "night_actions": len(self.night_actions),
            "speeches": len(self.day_speeches),
            "vote_result": self.vote_result.eliminated_id if self.vote_result else None,
            "eliminated": self.eliminated_player,
            "death_cause": self.death_cause
        }


@dataclass
class PlayerStatistics:
    """玩家统计信息"""
    player_id: int
    player_name: str
    role: str

    # 基础统计
    rounds_survived: int = 0
    is_alive_at_end: bool = False

    # 行动统计
    total_speeches: int = 0
    total_votes: int = 0
    correct_votes: int = 0  # 投给狼人的次数
    night_actions_taken: int = 0

    # 特殊角色统计
    check_count: int = 0  # 预言家查验次数
    correct_check_rate: float = 0.0  # 查验正确率
    save_count: int = 0  # 女巫救人次数
    poison_count: int = 0  # 女巫毒人次数
    kill_count: int = 0  # 狼人刀人次数
    shot_count: int = 0  # 猎人开枪次数

    # 认知准确度
    trust_accuracy: float = 0.0  # 信任判断准确率
    suspicion_accuracy: float = 0.0  # 怀疑判断准确率

    def to_dict(self) -> Dict:
        return {
            "player_id": self.player_id,
            "player_name": self.player_name,
            "role": self.role,
            "rounds_survived": self.rounds_survived,
            "is_alive_at_end": self.is_alive_at_end,
            "speeches": self.total_speeches,
            "votes": self.total_votes,
            "correct_votes": self.correct_votes,
            "vote_accuracy": self.correct_votes / self.total_votes if self.total_votes > 0 else 0,
            "night_actions": self.night_actions_taken,
            "special_stats": {
                "check_count": self.check_count,
                "correct_check_rate": self.correct_check_rate,
                "save_count": self.save_count,
                "poison_count": self.poison_count,
                "kill_count": self.kill_count,
                "shot_count": self.shot_count
            }
        }


@dataclass
class GameSummary:
    """游戏全局总结"""
    game_id: str
    start_time: datetime
    end_time: datetime
    total_rounds: int
    winner: str  # 'good' or 'werewolf'

    # 配置信息
    config: GameConfig

    # 玩家信息
    players: List[PlayerInfo]

    # 详细记录
    round_summaries: List[RoundSummary]
    player_statistics: Dict[int, PlayerStatistics]
    action_log: List[Action]

    # 关键事件
    key_moments: List[Dict]

    def to_dict(self) -> Dict:
        return {
            "game_id": self.game_id,
            "duration_seconds": (self.end_time - self.start_time).total_seconds(),
            "total_rounds": self.total_rounds,
            "winner": self.winner,
            "player_count": len(self.players),
            "player_statistics": {pid: stats.to_dict() for pid, stats in self.player_statistics.items()}
        }

    def generate_report(self) -> str:
        """生成人类可读的复盘报告"""
        report = []
        report.append("=" * 60)
        report.append(f"狼人杀游戏复盘报告 - {self.game_id}")
        report.append("=" * 60)
        report.append(f"游戏时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"总轮数: {self.total_rounds}")
        report.append(f"获胜方: {'好人阵营' if self.winner == 'good' else '狼人阵营'}")
        report.append("")

        # 玩家统计
        report.append("-" * 40)
        report.append("玩家统计")
        report.append("-" * 40)
        for stats in self.player_statistics.values():
            report.append(f"\n{stats.player_name} ({stats.role}):")
            report.append(f"  存活轮数: {stats.rounds_survived}")
            report.append(f"  发言次数: {stats.total_speeches}")
            report.append(f"  投票准确率: {stats.correct_votes}/{stats.total_votes}")
            if stats.check_count > 0:
                report.append(f"  查验次数: {stats.check_count}, 正确率: {stats.correct_check_rate:.1%}")
            if stats.kill_count > 0:
                report.append(f"  刀人次数: {stats.kill_count}")

        # 关键事件
        report.append("\n" + "-" * 40)
        report.append("关键事件时间线")
        report.append("-" * 40)
        for moment in self.key_moments:
            report.append(f"[轮次{moment.get('round', '?')}] {moment.get('description', '')}")

        report.append("\n" + "=" * 60)
        return "\n".join(report)


class GameStatsCollector:
    """
    游戏数据收集器
    负责收集和统计游戏过程中的所有数据
    """

    def __init__(self):
        self.reset()

    def reset(self):
        """重置所有数据"""
        self.round_actions: List[Action] = []
        self.round_speeches: List[Dict] = []
        self.round_votes: List[VoteResult] = []
        self.death_events: List[Dict] = []
        self.current_round = 0

    def start_new_round(self, round_num: int):
        """开始新的一轮"""
        self.current_round = round_num
        self.round_actions = []
        self.round_speeches = []

    def record_action(self, action: Action):
        """记录行动"""
        self.round_actions.append(action)

    def record_speech(self, player_id: int, content: str, round_num: int):
        """记录发言"""
        self.round_speeches.append({
            "round": round_num,
            "player": player_id,
            "content": content
        })

    def record_vote(self, vote_result: VoteResult):
        """记录投票结果"""
        self.round_votes.append(vote_result)

    def record_death(self, player_id: int, cause: str, round_num: int):
        """记录死亡事件"""
        self.death_events.append({
            "round": round_num,
            "player": player_id,
            "cause": cause
        })

    def get_round_summary(self) -> RoundSummary:
        """获取当前轮次总结"""
        return RoundSummary(
            round_num=self.current_round,
            night_actions=self.round_actions.copy(),
            day_speeches=self.round_speeches.copy(),
            vote_result=self.round_votes[-1] if self.round_votes else None
        )


class GameAnalyzer:
    """
    游戏分析器
    分析游戏数据，生成统计和复盘报告
    """

    def __init__(self):
        self.collector = GameStatsCollector()
        self.game_summary: Optional[GameSummary] = None

    def analyze_game(
            self,
            game_id: str,
            config: GameConfig,
            players: List[PlayerInfo],
            action_log: List[Action],
            vote_history: List[VoteResult],
            winner: str,
            start_time: datetime,
            end_time: datetime
    ) -> GameSummary:
        """
        分析完整游戏

        Args:
            game_id: 游戏ID
            config: 游戏配置
            players: 玩家列表
            action_log: 所有行动记录
            vote_history: 投票历史
            winner: 获胜方
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            游戏总结
        """
        # 计算总轮数
        total_rounds = max([a.round_num for a in action_log], default=0)

        # 计算玩家统计
        player_stats = self._calculate_player_statistics(players, action_log, vote_history)

        # 识别关键事件
        key_moments = self._identify_key_moments(action_log, vote_history)

        # 构建轮次总结
        round_summaries = self._build_round_summaries(action_log, vote_history)

        self.game_summary = GameSummary(
            game_id=game_id,
            start_time=start_time,
            end_time=end_time,
            total_rounds=total_rounds,
            winner=winner,
            config=config,
            players=players,
            round_summaries=round_summaries,
            player_statistics=player_stats,
            action_log=action_log,
            key_moments=key_moments
        )

        return self.game_summary

    def _calculate_player_statistics(
            self,
            players: List[PlayerInfo],
            action_log: List[Action],
            vote_history: List[VoteResult]
    ) -> Dict[int, PlayerStatistics]:
        """计算玩家统计信息"""
        stats = {}

        # 初始化统计
        for player in players:
            stats[player.player_id] = PlayerStatistics(
                player_id=player.player_id,
                player_name=player.player_name,
                role=player.role.value
            )

        # 统计行动
        for action in action_log:
            stat = stats.get(action.player_id)
            if not stat:
                continue

            if action.action_type == ActionType.SPEAK:
                stat.total_speeches += 1
            elif action.action_type == ActionType.VOTE:
                stat.total_votes += 1
            elif action.action_type == ActionType.CHECK:
                stat.check_count += 1
                stat.night_actions_taken += 1
            elif action.action_type == ActionType.SAVE:
                stat.save_count += 1
                stat.night_actions_taken += 1
            elif action.action_type == ActionType.POISON:
                stat.poison_count += 1
                stat.night_actions_taken += 1
            elif action.action_type == ActionType.KILL:
                stat.kill_count += 1
                stat.night_actions_taken += 1
            elif action.action_type == ActionType.SHOOT:
                stat.shot_count += 1

        # 统计投票准确率（需要知道谁是狼人）
        # 简化实现：这里需要外部传入狼人列表
        # 实际使用时需要补充

        # 计算存活轮数
        max_round = max([a.round_num for a in action_log], default=0)
        for stat in stats.values():
            stat.rounds_survived = max_round

        return stats

    def _identify_key_moments(self, action_log: List[Action], vote_history: List[VoteResult]) -> List[Dict]:
        """识别关键事件"""
        key_moments = []

        # 识别查杀时刻
        check_actions = [a for a in action_log if a.action_type == ActionType.CHECK]
        for action in check_actions:
            key_moments.append({
                "round": action.round_num,
                "type": "check",
                "description": f"预言家查验了{action.target_id}号玩家"
            })

        # 识别投票放逐
        for vote in vote_history:
            if vote.eliminated_id:
                key_moments.append({
                    "round": vote.round_num,
                    "type": "elimination",
                    "description": f"{vote.eliminated_id}号玩家被投票放逐"
                })

        # 识别开枪
        shoot_actions = [a for a in action_log if a.action_type == ActionType.SHOOT]
        for action in shoot_actions:
            key_moments.append({
                "round": action.round_num,
                "type": "shoot",
                "description": f"猎人开枪带走了{action.target_id}号玩家"
            })

        return key_moments

    def _build_round_summaries(
            self,
            action_log: List[Action],
            vote_history: List[VoteResult]
    ) -> List[RoundSummary]:
        """构建轮次总结"""
        round_summaries = []

        # 按轮次分组
        max_round = max([a.round_num for a in action_log], default=0)
        for round_num in range(1, max_round + 1):
            round_actions = [a for a in action_log if a.round_num == round_num]
            round_votes = [v for v in vote_history if v.round_num == round_num]

            summary = RoundSummary(
                round_num=round_num,
                night_actions=round_actions,
                vote_result=round_votes[0] if round_votes else None
            )
            round_summaries.append(summary)

        return round_summaries


class ReportGenerator:
    """
    报告生成器
    生成格式化的复盘报告
    """

    def __init__(self):
        self.analyzer = GameAnalyzer()

    def generate_full_report(self, game_summary: GameSummary) -> str:
        """生成完整复盘报告"""
        return game_summary.generate_report()

    def generate_json_report(self, game_summary: GameSummary) -> str:
        """生成JSON格式报告"""
        return json.dumps(game_summary.to_dict(), indent=2, ensure_ascii=False)

    def generate_leaderboard(self, game_histories: List[GameSummary]) -> str:
        """
        生成排行榜

        Args:
            game_histories: 多局游戏历史

        Returns:
            排行榜文本
        """
        # 统计各角色胜率
        role_winrates = defaultdict(lambda: {"wins": 0, "games": 0})

        for game in game_histories:
            for player in game.players:
                role = player.role.value
                role_winrates[role]["games"] += 1
                if game.winner == "good" and player.role.is_good():
                    role_winrates[role]["wins"] += 1
                elif game.winner == "werewolf" and not player.role.is_good():
                    role_winrates[role]["wins"] += 1

        report = []
        report.append("=" * 50)
        report.append("狼人杀Agent排行榜")
        report.append("=" * 50)
        report.append("")
        report.append("各角色胜率:")
        for role, stats in sorted(role_winrates.items()):
            win_rate = stats["wins"] / stats["games"] if stats["games"] > 0 else 0
            report.append(f"  {role}: {win_rate:.1%} ({stats['wins']}/{stats['games']})")

        return "\n".join(report)

    def generate_comparison_report(
            self,
            game_summaries: List[GameSummary],
            agent_versions: Dict[int, str]
    ) -> str:
        """
        生成不同版本Agent的对比报告

        Args:
            game_summaries: 多局游戏总结
            agent_versions: Agent版本映射 {player_id: version}

        Returns:
            对比报告
        """
        # 按版本分组统计
        version_stats = defaultdict(lambda: {"wins": 0, "games": 0, "avg_survival": 0})

        for game in game_summaries:
            for pid, stats in game.player_statistics.items():
                version = agent_versions.get(pid, "unknown")
                version_stats[version]["games"] += 1

                if game.winner == "good" and stats.role in ["villager", "seer", "witch", "hunter"]:
                    version_stats[version]["wins"] += 1
                elif game.winner == "werewolf" and stats.role == "werewolf":
                    version_stats[version]["wins"] += 1

                version_stats[version]["avg_survival"] += stats.rounds_survived

        # 计算平均值
        for version in version_stats:
            games = version_stats[version]["games"]
            if games > 0:
                version_stats[version]["avg_survival"] /= games

        report = []
        report.append("=" * 60)
        report.append("Agent版本对比报告")
        report.append("=" * 60)
        report.append("")
        report