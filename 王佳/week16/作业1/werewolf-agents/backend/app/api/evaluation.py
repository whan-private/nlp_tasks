from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.action import Action
from app.models.game import Game, Player
from app.models.log import GameLog
from app.services.evaluator import Evaluator

router = APIRouter(prefix="/api/evaluation", tags=["评测系统"])

evaluator = Evaluator()


class CompareRequest(BaseModel):
    game_ids: list[str]


@router.get("/{game_id}/report")
def get_game_report(game_id: str, db: Session = Depends(get_db)):
    """获取单局游戏的详细评测报告。"""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")
    if game.status != "finished":
        raise HTTPException(status_code=400, detail="游戏尚未结束，无法生成评测报告")

    # 获取玩家数据
    players = db.query(Player).filter(Player.game_id == game_id).all()
    players_data = [
        {"id": p.id, "role": p.role, "team": p.team, "is_alive": p.is_alive}
        for p in players
    ]

    # 获取游戏日志
    logs = db.query(GameLog).filter(GameLog.game_id == game_id).order_by(GameLog.timestamp).all()
    logs_data = [
        {"event": l.event, "data": l.data}
        for l in logs
    ]

    # 评测
    metrics = evaluator.evaluate_game(logs_data, players_data)
    report = evaluator.generate_report(metrics)

    return report


@router.get("/leaderboard")
def get_leaderboard(limit: int = 20, db: Session = Depends(get_db)):
    """获取 Agent 排行榜。"""
    finished_games = db.query(Game).filter(Game.status == "finished").limit(100).all()

    all_metrics = []
    for game in finished_games:
        players = db.query(Player).filter(Player.game_id == game.id).all()
        logs = db.query(GameLog).filter(GameLog.game_id == game.id).order_by(GameLog.timestamp).all()

        players_data = [
            {"id": p.id, "role": p.role, "team": p.team, "is_alive": p.is_alive}
            for p in players
        ]
        logs_data = [{"event": l.event, "data": l.data} for l in logs]

        metrics = evaluator.evaluate_game(logs_data, players_data)
        metrics.game_id = game.id
        all_metrics.append(metrics)

    leaderboard = evaluator.build_leaderboard(all_metrics)
    return {
        "leaderboard": leaderboard[:limit],
        "total_games": len(finished_games),
    }


@router.post("/compare")
def compare_games(req: CompareRequest, db: Session = Depends(get_db)):
    """多局对比分析。"""
    if len(req.game_ids) < 2:
        raise HTTPException(status_code=400, detail="至少需要 2 局游戏才能对比")

    all_metrics = []
    for game_id in req.game_ids:
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game:
            raise HTTPException(status_code=404, detail=f"游戏 {game_id} 不存在")

        players = db.query(Player).filter(Player.game_id == game_id).all()
        logs = db.query(GameLog).filter(GameLog.game_id == game_id).order_by(GameLog.timestamp).all()

        players_data = [
            {"id": p.id, "role": p.role, "team": p.team, "is_alive": p.is_alive}
            for p in players
        ]
        logs_data = [{"event": l.event, "data": l.data} for l in logs]

        metrics = evaluator.evaluate_game(logs_data, players_data)
        metrics.game_id = game_id
        all_metrics.append(metrics)

    result = evaluator.compare_games(req.game_ids, all_metrics)
    return result


@router.get("/stats")
def get_overall_stats(db: Session = Depends(get_db)):
    """获取整体统计数据。"""
    total = db.query(Game).count()
    finished = db.query(Game).filter(Game.status == "finished").count()
    playing = db.query(Game).filter(Game.status == "playing").count()
    pending = db.query(Game).filter(Game.status == "pending").count()

    villager_wins = db.query(Game).filter(Game.status == "finished", Game.winner == "villager").count()
    werewolf_wins = db.query(Game).filter(Game.status == "finished", Game.winner == "werewolf").count()

    total_finished = villager_wins + werewolf_wins
    villager_rate = (villager_wins / total_finished * 100) if total_finished > 0 else 0
    werewolf_rate = (werewolf_wins / total_finished * 100) if total_finished > 0 else 0

    return {
        "total_games": total,
        "finished": finished,
        "playing": playing,
        "pending": pending,
        "win_rate": {
            "villager": round(villager_rate, 1),
            "werewolf": round(werewolf_rate, 1),
        },
    }
