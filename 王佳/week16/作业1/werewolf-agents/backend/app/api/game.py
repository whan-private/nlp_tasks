"""游戏管理 API — 创建、控制、查询游戏。"""

import random

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.schemas import (
    CreateGameRequest,
    DeadPlayerInfo,
    GameControlResponse,
    GameCreatedResponse,
    GameListResponse,
    GameListItem,
    GameReplayResponse,
    GameResultResponse,
    GameStateResponse,
    GameStatsResponse,
    LogEntry,
    PlayerInfo,
    RoundReplay,
    StartGameRequest,
)
from app.core.database import get_db
from app.models.game import Game, Player
from app.services.agent_manager import AgentManager
from app.services.game_engine import GameEngine
from app.services.role_system import get_default_composition

router = APIRouter(prefix="/api/game", tags=["游戏管理"])

# 内存中的游戏引擎实例
_active_games: dict[str, GameEngine] = {}


# ==================== 辅助 ====================

def _engine_or_404(game_id: str) -> GameEngine:
    engine = _active_games.get(game_id)
    if not engine:
        raise HTTPException(status_code=404, detail="游戏不存在或未启动")
    return engine


def _player_to_info(p: dict) -> PlayerInfo:
    """将引擎内部玩家字典转为 PlayerInfo。"""
    return PlayerInfo(
        id=p.get("id", ""),
        name=p.get("name", p.get("id", "")),
        role=p.get("role", "unknown"),
        team=p.get("team", "unknown"),
        is_alive=True,
    )


# ==================== 创建 & 启动 ====================

@router.post("", response_model=GameCreatedResponse, status_code=201)
def create_game(req: CreateGameRequest, db: Session = Depends(get_db)):
    """创建新游戏，返回 game_id 和玩家列表。"""
    try:
        composition = get_default_composition(req.player_count)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    role_list = []
    for role_name, count in composition.items():
        role_list.extend([role_name] * count)
    random.shuffle(role_list)

    ai_count = req.player_count - req.human_players
    players = []
    for i, role_name in enumerate(role_list):
        is_ai = i < ai_count
        name = f"AI-{i+1}" if is_ai else f"玩家-{i+1}"
        players.append(Player(
            name=name, role=role_name, is_ai=is_ai,
            team="werewolf" if role_name == "werewolf" else "villager",
        ))

    game = Game(
        status="pending",
        config={"player_count": req.player_count, "composition": composition, "mode": req.mode},
    )
    db.add(game)
    db.flush()

    for p in players:
        p.game_id = game.id
        db.add(p)
    db.commit()

    player_infos = [
        PlayerInfo(id=p.id, name=p.name, role=p.role, team=p.team, is_alive=True)
        for p in players
    ]
    return GameCreatedResponse(
        game_id=game.id,
        status="pending",
        mode=req.mode,
        players=player_infos,
    )


@router.post("/{game_id}/start", response_model=GameControlResponse)
async def start_game(
    game_id: str,
    req: StartGameRequest = StartGameRequest(),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    """开始游戏（后台异步运行）。"""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")
    if game.status == "finished":
        raise HTTPException(status_code=400, detail="游戏已结束")
    if game.status == "playing":
        if game_id in _active_games:
            raise HTTPException(status_code=400, detail="游戏已经在运行中")

    players = db.query(Player).filter(Player.game_id == game_id).all()
    if not players:
        raise HTTPException(status_code=400, detail="游戏中没有玩家")

    # 检测是否为断点续玩
    is_resume = (game.status == "playing" and game.engine_state is not None)
    resume_mode = game.config.get("mode", req.mode) if game.config else req.mode

    player_roles = {p.id: {"role": p.role, "name": p.name} for p in players}
    agent_manager = AgentManager(game_id)
    engine = GameEngine(game_id, agent_manager, mode=req.mode if not is_resume else resume_mode)
    _active_games[game_id] = engine

    game.status = "playing"
    db.commit()

    background_tasks.add_task(engine.run, player_roles, resume=is_resume)

    if is_resume:
        label = "手动" if resume_mode == "manual" else "自动"
        return GameControlResponse(
            game_id=game_id, action="resume", status="playing", mode=resume_mode,
            message=f"游戏已从断点恢复（第{game.round}轮，{label}模式）",
        )
    label = "手动" if req.mode == "manual" else "自动"
    return GameControlResponse(
        game_id=game_id, action="start", status="playing", mode=req.mode,
        message=f"游戏已启动（{label}模式）",
    )


# ==================== 控制操作 ====================

@router.post("/{game_id}/pause", response_model=GameControlResponse)
def pause_game(game_id: str):
    engine = _engine_or_404(game_id)
    engine.pause()
    return GameControlResponse(
        game_id=game_id, action="pause", status="paused", mode=engine.mode,
        message="游戏已暂停",
    )


@router.post("/{game_id}/resume", response_model=GameControlResponse)
def resume_game(game_id: str):
    engine = _engine_or_404(game_id)
    engine.resume()
    return GameControlResponse(
        game_id=game_id, action="resume", status="running", mode=engine.mode,
        message="游戏已恢复",
    )


@router.post("/{game_id}/stop", response_model=GameControlResponse)
def stop_game(game_id: str, db: Session = Depends(get_db)):
    engine = _active_games.get(game_id)
    if engine:
        engine.stop()
        return GameControlResponse(
            game_id=game_id, action="stop", status="stopped", mode=engine.mode,
            message="游戏已停止",
        )
    # 引擎不存在但游戏在数据库中是 playing 状态（服务器重启后丢失引擎）
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")
    if game.status == "playing":
        game.status = "finished"
        db.commit()
        return GameControlResponse(
            game_id=game_id, action="stop", status="finished", mode="auto",
            message="游戏已终止（引擎已丢失，状态已重置）",
        )
    raise HTTPException(status_code=400, detail="游戏未在运行中")


@router.post("/{game_id}/step", response_model=GameControlResponse)
def step_game(game_id: str):
    engine = _engine_or_404(game_id)
    engine.step()
    return GameControlResponse(
        game_id=game_id, action="step", status="stepping", mode=engine.mode,
        message="单步推进中",
    )


@router.post("/{game_id}/mode", response_model=GameControlResponse)
def set_game_mode(game_id: str, mode: str = Query(..., pattern="^(auto|manual)$")):
    """切换游戏模式。"""
    engine = _engine_or_404(game_id)
    try:
        engine.set_mode(mode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    label = "手动" if mode == "manual" else "自动"
    return GameControlResponse(
        game_id=game_id, action="set_mode",
        status="paused" if engine.is_paused else "running", mode=mode,
        message=f"已切换到{label}模式",
    )


# ==================== 状态 & 结果 ====================

@router.get("/{game_id}/state", response_model=GameStateResponse)
def get_game_state(game_id: str, db: Session = Depends(get_db)):
    """获取游戏当前状态（含完整的中间结果）。"""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")

    engine = _active_games.get(game_id)
    if engine:
        raw = engine.get_public_state()
        # 将内部字典转为结构化模型
        alive = [
            PlayerInfo(
                id=p.get("id", ""),
                name=p.get("name", p.get("id", "")),
                role=p.get("role", "unknown"),
                team=p.get("team", "unknown"),
                is_alive=True,
            )
            for p in raw.get("alive_players", [])
        ]
        dead = [
            {"player_id": d.get("player_id", ""), "name": d.get("name", ""), "role": d.get("role", ""),
             "team": d.get("team", ""), "cause": d.get("cause", ""), "round": d.get("round", 0)}
            for d in raw.get("dead_players", [])
        ]
        recent_logs = [
            LogEntry(timestamp=log.get("timestamp", ""), event=log.get("event", ""), message=log.get("message", ""))
            for log in raw.get("recent_logs", [])
        ]
        return GameStateResponse(
            game_id=raw["game_id"],
            status=game.status,
            round=raw["round"],
            phase=raw["phase"],
            mode=raw.get("mode", "auto"),
            is_paused=raw["is_paused"],
            is_running=raw["is_running"],
            winner=raw.get("winner"),
            alive_players=alive,
            dead_players=dead,
            phase_details=raw.get("phase_details", {}),
            recent_logs=recent_logs,
        )

    # 引擎不存在时的回退
    display_status = game.status
    if display_status == "playing":
        # 有保存的检查点 → 可恢复状态
        if game.engine_state:
            display_status = "paused"
        else:
            display_status = "pending"

    players_data = db.query(Player).filter(Player.game_id == game_id).all()

    # 如果有保存的检查点，从检查点恢复玩家存活状态
    if game.engine_state:
        es = game.engine_state
        saved_state = es.get("state", {})
        alive_ids = {p["id"] for p in saved_state.get("alive_players", [])}
        dead_map = {d["player_id"]: d for d in saved_state.get("dead_players", [])}
        alive = []
        dead = []
        for p in players_data:
            if p.id in alive_ids:
                alive.append(PlayerInfo(id=p.id, name=p.name, role=p.role, team=p.team, is_alive=True))
            else:
                cause = dead_map.get(p.id, {}).get("cause", "unknown") if p.id in dead_map else "unknown"
                dead.append(DeadPlayerInfo(
                    player_id=p.id, name=p.name, role=p.role, team=p.team,
                    cause=cause,
                ))
        recent_logs = [
            LogEntry(timestamp=log.get("timestamp", ""), event=log.get("event", ""), message=log.get("message", ""))
            for log in es.get("logs", [])[-60:]
        ]
        mode = game.config.get("mode", "auto") if game.config else "auto"
        return GameStateResponse(
            game_id=game.id,
            status=display_status,
            round=game.round or 0,
            phase=game.phase or "",
            mode=mode,
            is_paused=True, is_running=False,
            winner=game.winner,
            alive_players=alive,
            dead_players=dead,
            phase_details={},
            recent_logs=recent_logs,
        )

    alive = [
        PlayerInfo(id=p.id, name=p.name, role=p.role, team=p.team, is_alive=p.is_alive)
        for p in players_data
    ]
    return GameStateResponse(
        game_id=game.id,
        status=display_status,
        round=0, phase="", mode="auto",
        is_paused=False, is_running=False,
        winner=game.winner,
        alive_players=alive,
        dead_players=[],
        phase_details={},
    )


@router.get("/{game_id}/result", response_model=GameResultResponse)
def get_game_result(game_id: str, db: Session = Depends(get_db)):
    """获取游戏最终结果。"""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")

    engine = _active_games.get(game_id)
    if engine:
        raw = engine.get_result()
        players = [
            PlayerInfo(
                id=p.get("id", ""),
                name=p.get("name", p.get("id", "")),
                role=p.get("role", "unknown"),
                team=p.get("team", "unknown"),
                is_alive=p.get("is_alive", True),
            )
            for p in raw.get("players", [])
        ]
        logs = [
            LogEntry(timestamp=l.get("timestamp", ""), event=l.get("event", ""), message=l.get("message", ""))
            for l in raw.get("logs", [])
        ]
        return GameResultResponse(
            game_id=raw["game_id"],
            winner=raw.get("winner"),
            total_rounds=raw.get("total_rounds", 0),
            players=players,
            logs=logs,
        )

    players_data = db.query(Player).filter(Player.game_id == game_id).all()
    players = [
        PlayerInfo(id=p.id, name=p.name, role=p.role, team=p.team, is_alive=p.is_alive)
        for p in players_data
    ]
    return GameResultResponse(
        game_id=game.id,
        winner=game.winner,
        total_rounds=0,
        players=players,
        logs=[],
    )


# ==================== 对局复盘 ====================

@router.get("/{game_id}/replay", response_model=GameReplayResponse)
def get_game_replay(game_id: str, db: Session = Depends(get_db)):
    """获取完整对局复盘（按回合组织的事件时间线）。"""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")

    players_data = db.query(Player).filter(Player.game_id == game_id).all()
    player_infos = [
        PlayerInfo(id=p.id, name=p.name, role=p.role, team=p.team, is_alive=p.is_alive)
        for p in players_data
    ]

    engine = _active_games.get(game_id)
    if engine:
        raw = engine.get_result()
        logs = raw.get("logs", [])
    else:
        from app.models.log import GameLog
        db_logs = db.query(GameLog).filter(GameLog.game_id == game_id).order_by(GameLog.timestamp).all()
        logs = [
            {"timestamp": str(l.timestamp) if l.timestamp else "", "event": l.event, "message": ""}
            for l in db_logs
        ]

    # 按回合组织
    rounds_map: dict[int, list[LogEntry]] = {}
    for log in logs:
        # 尝试从 message 中提取 round 信息
        entry = LogEntry(
            timestamp=log.get("timestamp", ""),
            event=log.get("event", ""),
            message=log.get("message", ""),
        )
        # 简单按顺序分组（实际的 round 信息在日志中可能不完整）
        r = 0
        for key in log:
            if key == "round":
                r = log[key]
                break
        if r not in rounds_map:
            rounds_map[r] = []
        rounds_map[r].append(entry)

    rounds = [
        RoundReplay(round=r, phase="night" if r > 0 else "", events=events)
        for r, events in sorted(rounds_map.items())
    ]

    return GameReplayResponse(
        game_id=game.id,
        winner=game.winner,
        total_rounds=len(rounds),
        players=player_infos,
        rounds=rounds,
    )


# ==================== 列表 & 统计 ====================

@router.get("/list", response_model=GameListResponse)
def list_games(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """列出最近的游戏。"""
    total = db.query(Game).count()
    games = db.query(Game).order_by(Game.created_at.desc()).limit(limit).all()
    items = [
        GameListItem(
            id=g.id,
            status=g.status,
            player_count=g.config.get("player_count", 0) if g.config else 0,
            created_at=g.created_at.isoformat() if g.created_at else None,
            winner=g.winner,
        )
        for g in games
    ]
    return GameListResponse(games=items, total=total)


@router.get("/stats", response_model=GameStatsResponse)
def get_game_stats(db: Session = Depends(get_db)):
    """获取整体统计数据。"""
    total = db.query(Game).count()
    finished = db.query(Game).filter(Game.status == "finished").count()
    playing = db.query(Game).filter(Game.status == "playing").count()
    pending = db.query(Game).filter(Game.status == "pending").count()

    villager_wins = db.query(Game).filter(Game.status == "finished", Game.winner == "villager").count()
    werewolf_wins = db.query(Game).filter(Game.status == "finished", Game.winner == "werewolf").count()
    total_finished = villager_wins + werewolf_wins
    villager_rate = round(villager_wins / total_finished * 100, 1) if total_finished > 0 else 0
    werewolf_rate = round(werewolf_wins / total_finished * 100, 1) if total_finished > 0 else 0

    return GameStatsResponse(
        total_games=total,
        finished=finished,
        playing=playing,
        pending=pending,
        win_rate={"villager": villager_rate, "werewolf": werewolf_rate},
    )
