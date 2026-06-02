from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.action import Action
from app.models.game import Game, Player

router = APIRouter(prefix="/api/game", tags=["玩家操作"])


class PlayerActionRequest(BaseModel):
    action_type: str  # kill/check/save/poison/vote/speak
    target_id: str | None = None
    content: str | None = None
    reasoning: str | None = None


class PlayerSpeakRequest(BaseModel):
    content: str


@router.post("/{game_id}/player/{player_id}/action")
def player_action(game_id: str, player_id: str, req: PlayerActionRequest, db: Session = Depends(get_db)):
    """人类玩家执行操作。"""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")

    player = db.query(Player).filter(Player.id == player_id, Player.game_id == game_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="玩家不存在")
    if player.is_ai:
        raise HTTPException(status_code=400, detail="不能操作 AI 玩家")
    if not player.is_alive:
        raise HTTPException(status_code=400, detail="玩家已死亡")

    action = Action(
        game_id=game_id,
        round=0,  # 由游戏引擎填充
        phase="day",
        actor_id=player_id,
        action_type=req.action_type,
        target_id=req.target_id,
        content=req.content or req.reasoning,
    )
    db.add(action)
    db.commit()

    return {"status": "ok", "action_id": action.id}


@router.post("/{game_id}/player/{player_id}/speak")
def player_speak(game_id: str, player_id: str, req: PlayerSpeakRequest, db: Session = Depends(get_db)):
    """人类玩家发言。"""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")

    player = db.query(Player).filter(Player.id == player_id, Player.game_id == game_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="玩家不存在")
    if not player.is_alive:
        raise HTTPException(status_code=400, detail="玩家已死亡")

    action = Action(
        game_id=game_id,
        round=0,
        phase="day",
        actor_id=player_id,
        action_type="speak",
        content=req.content,
    )
    db.add(action)
    db.commit()

    return {"status": "ok", "action_id": action.id}
