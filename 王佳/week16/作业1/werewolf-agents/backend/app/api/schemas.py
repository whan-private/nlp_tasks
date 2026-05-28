"""API 请求/响应 Pydantic 模型 — 所有接口的输入输出结构定义。"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


# ==================== 玩家 ====================

class PlayerInfo(BaseModel):
    """玩家公开信息。"""
    id: str
    name: str
    role: str
    team: str
    is_alive: bool = True


class DeadPlayerInfo(BaseModel):
    """死亡玩家信息。"""
    player_id: str
    name: str = ""
    role: str = ""
    team: str = ""
    cause: str = ""
    round: int = 0


# ==================== 游戏日志 ====================

class LogEntry(BaseModel):
    """单条游戏事件日志。"""
    timestamp: str = ""
    event: str = ""
    message: str = ""


# ==================== 创建 & 启动 ====================

class CreateGameRequest(BaseModel):
    """创建游戏请求。"""
    player_count: int = Field(default=9, description="总玩家数（6/9/12）")
    human_players: int = Field(default=0, ge=0, description="人类玩家数")
    mode: str = Field(default="auto", pattern="^(auto|manual)$", description="游戏模式")

    @field_validator("player_count")
    @classmethod
    def validate_player_count(cls, v: int) -> int:
        if v not in (6, 9, 12):
            raise ValueError("player_count 必须是 6、9 或 12")
        return v

    @field_validator("human_players")
    @classmethod
    def validate_human_players(cls, v: int, info) -> int:
        if "player_count" in info.data and v > info.data["player_count"]:
            raise ValueError("human_players 不能超过 player_count")
        return v


class GameCreatedResponse(BaseModel):
    """创建游戏响应。"""
    game_id: str
    status: str
    mode: str
    players: list[PlayerInfo]


class StartGameRequest(BaseModel):
    """启动游戏请求。"""
    mode: str = Field(default="auto", pattern="^(auto|manual)$")


# ==================== 控制操作 ====================

class GameControlResponse(BaseModel):
    """控制操作响应（暂停/恢复/停止/单步/切换模式 通用）。"""
    game_id: str
    action: str
    status: str
    mode: str
    message: str


# ==================== 状态查询 ====================

class PhaseDetails(BaseModel):
    """当前阶段详情。"""
    type: str = ""       # "night" | "day"
    stage: str = ""      # 子阶段
    round: int = 0
    deaths: list[str] = []
    saved: str | None = None
    player_id: str = ""


class GameStateResponse(BaseModel):
    """游戏当前状态。"""
    game_id: str
    status: str
    round: int
    phase: str
    mode: str
    is_paused: bool
    is_running: bool
    winner: str | None
    alive_players: list[PlayerInfo]
    dead_players: list[DeadPlayerInfo]
    phase_details: dict = {}
    recent_logs: list[LogEntry] = []


# ==================== 最终结果 ====================

class GameResultResponse(BaseModel):
    """游戏最终结果。"""
    game_id: str
    winner: str | None
    total_rounds: int
    players: list[PlayerInfo]
    logs: list[LogEntry]


# ==================== 对局复盘 ====================

class RoundReplay(BaseModel):
    """单轮复盘。"""
    round: int
    phase: str
    events: list[LogEntry]


class GameReplayResponse(BaseModel):
    """完整对局复盘。"""
    game_id: str
    winner: str | None
    total_rounds: int
    players: list[PlayerInfo]
    rounds: list[RoundReplay]
    summaries: list[dict] = []


# ==================== 游戏列表 ====================

class GameListItem(BaseModel):
    """游戏列表条目。"""
    id: str
    status: str
    player_count: int = 0
    created_at: str | None = None
    winner: str | None = None


class GameListResponse(BaseModel):
    """游戏列表响应。"""
    games: list[GameListItem]
    total: int = 0


# ==================== 统计 ====================

class GameStatsResponse(BaseModel):
    """整体统计数据。"""
    total_games: int
    finished: int
    playing: int
    pending: int
    win_rate: dict[str, float]


# ==================== 健康检查 ====================

class HealthResponse(BaseModel):
    """健康检查响应。"""
    status: str
    version: str = "1.0.0"
