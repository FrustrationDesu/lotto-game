from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.storage.models import Game, GamePlayer, GameResult


@dataclass
class GlobalBalance:
    total_net: float
    games_count: int


def record_finished_game(game_id: int, db: Session) -> None:
    game = db.get(Game, game_id)
    if game is None:
        raise ValueError(f"Game {game_id} not found")
    if game.status != "finished":
        raise ValueError(f"Game {game_id} is not finished")

    db.query(GameResult).filter(GameResult.game_id == game_id).delete(synchronize_session=False)

    players = db.scalars(select(GamePlayer).where(GamePlayer.game_id == game_id)).all()
    for player in players:
        db.add(
            GameResult(
                game_id=game_id,
                player_name=player.player_name,
                net=player.payout - player.buy_in,
                card_closed=player.card_closed,
            )
        )

    db.commit()


def get_global_balance(
    db: Session,
    *,
    period_days: int | None = None,
    player_name: str | None = None,
) -> GlobalBalance:
    filters = [Game.status == "finished"]
    if period_days is not None:
        since = datetime.utcnow() - timedelta(days=period_days)
        filters.append(Game.finished_at >= since)
    if player_name is not None:
        filters.append(GameResult.player_name == player_name)

    row = db.execute(
        select(func.coalesce(func.sum(GameResult.net), 0.0), func.count(func.distinct(GameResult.game_id)))
        .join(Game, Game.id == GameResult.game_id)
        .where(and_(*filters))
    ).one()

    return GlobalBalance(total_net=float(row[0] or 0.0), games_count=int(row[1] or 0))
