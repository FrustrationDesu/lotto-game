from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.api.errors import api_error
from app.services.stats_service import get_global_balance
from app.storage.database import get_db
from app.storage.models import Game, GameResult

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/balance")
def stats_balance(
    period_days: int | None = Query(default=None, ge=1),
    player: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    try:
        balance = get_global_balance(db, period_days=period_days, player_name=player)
    except RuntimeError as exc:
        raise api_error(code="stats_unavailable", message=str(exc), status_code=503) from exc

    per_player = db.execute(
        select(GameResult.player_name, func.coalesce(func.sum(GameResult.net), 0.0).label("net"))
        .join(Game, Game.id == GameResult.game_id)
        .where(Game.status == "finished")
        .group_by(GameResult.player_name)
        .order_by(GameResult.player_name)
    ).all()

    players = {row.player_name: float(row.net) for row in per_player}
    average = balance.total_net / balance.games_count if balance.games_count else 0.0
    return {
        "total_balance": balance.total_net,
        "games_count": balance.games_count,
        "average_per_game": average,
        "players": [{"name": name, "net": net} for name, net in players.items()],
        # backward compatibility for old contract
        "games_finished": balance.games_count,
        "global_balance": players,
    }


@router.get("/player/{name}")
def player_stats(name: str, db: Session = Depends(get_db)) -> dict:
    history = db.execute(
        select(
            GameResult.game_id,
            Game.finished_at,
            GameResult.net,
            GameResult.card_closed,
        )
        .join(Game, Game.id == GameResult.game_id)
        .where(and_(Game.status == "finished", GameResult.player_name == name))
        .order_by(Game.finished_at.desc().nullslast(), GameResult.game_id.desc())
    ).all()

    totals = db.execute(
        select(
            func.coalesce(func.sum(GameResult.net), 0.0),
            func.count(GameResult.id),
            func.coalesce(func.sum(case((GameResult.card_closed.is_(True), 1), else_=0)), 0),
        )
        .join(Game, Game.id == GameResult.game_id)
        .where(and_(Game.status == "finished", GameResult.player_name == name))
    ).one()

    total_net = float(totals[0] or 0.0)
    games_count = int(totals[1] or 0)
    wins = int(totals[2] or 0)

    return {
        "player": name,
        "total_net": total_net,
        "games_count": games_count,
        "win_rate": (wins / games_count) if games_count else 0.0,
        "history": [
            {
                "game_id": row.game_id,
                "finished_at": row.finished_at.isoformat() if isinstance(row.finished_at, datetime) else None,
                "net": float(row.net),
                "card_closed": row.card_closed,
            }
            for row in history
        ],
    }
