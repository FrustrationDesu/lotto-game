from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

try:
    from sqlalchemy import and_, func, select
    from sqlalchemy.orm import Session

    from app.storage.models import Game, GamePlayer, GameResult
    SQLALCHEMY_READY = True
except ModuleNotFoundError:  # pragma: no cover - fallback for minimal environments
    Session = Any  # type: ignore
    SQLALCHEMY_READY = False


@dataclass
class GlobalBalance:
    total_net: float
    games_count: int


@dataclass
class AggregateStats:
    total_games: int
    finished_games: int


class StatsService:
    """Lightweight aggregation service used by unit-tests and admin scripts."""

    def aggregate(self, games: list[object]) -> dict[str, int]:
        total_games = len(games)
        finished_games = sum(1 for game in games if getattr(game, "status", None) == "finished")
        return {"total_games": total_games, "finished_games": finished_games}


def record_finished_game(game_id: int, db: Session) -> None:
    if not SQLALCHEMY_READY:
        raise RuntimeError("SQLAlchemy is required for record_finished_game")

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
    if not SQLALCHEMY_READY:
        raise RuntimeError("SQLAlchemy is required for get_global_balance")

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
