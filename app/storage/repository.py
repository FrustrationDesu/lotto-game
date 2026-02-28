from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.domain import GameEventType
from app.storage.models import Game, GameEvent, GamePlayer, GameResult


@dataclass(slots=True)
class GameRow:
    id: int
    players: list[str]
    card_price_kopecks: int
    line_bonus_kopecks: int
    line_winners: list[str]
    card_winners: list[str]
    finished_at: str | None


class LottoRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create_game(self, players: list[str], card_price_kopecks: int, line_bonus_kopecks: int) -> int:
        with self._session_factory() as db:
            game = Game(
                status="active",
                card_price_kopecks=card_price_kopecks,
                line_bonus_kopecks=line_bonus_kopecks,
            )
            db.add(game)
            db.flush()
            db.add_all([GamePlayer(game_id=game.id, player_name=player, buy_in=float(card_price_kopecks)) for player in players])
            db.commit()
            return game.id

    def get_game(self, game_id: int) -> GameRow | None:
        with self._session_factory() as db:
            game = db.get(Game, game_id)
            if game is None:
                return None

            players = db.scalars(
                select(GamePlayer.player_name).where(GamePlayer.game_id == game_id).order_by(GamePlayer.id)
            ).all()
            line_winners = db.scalars(
                select(GameEvent.player_name)
                .where(GameEvent.game_id == game_id, GameEvent.event_type == GameEventType.LINE_CLOSED.value)
                .order_by(GameEvent.id)
            ).all()
            card_winners = db.scalars(
                select(GameEvent.player_name)
                .where(GameEvent.game_id == game_id, GameEvent.event_type == GameEventType.CARD_CLOSED.value)
                .order_by(GameEvent.id)
            ).all()

            finished_at = game.finished_at.astimezone(timezone.utc).isoformat() if game.finished_at else None
            return GameRow(
                id=game.id,
                players=list(players),
                card_price_kopecks=game.card_price_kopecks,
                line_bonus_kopecks=game.line_bonus_kopecks,
                line_winners=[winner for winner in line_winners if winner],
                card_winners=[winner for winner in card_winners if winner],
                finished_at=finished_at,
            )

    def append_winners(self, game_id: int, event_type: GameEventType, winners: list[str]) -> None:
        with self._session_factory() as db:
            for winner in winners:
                db.add(GameEvent(game_id=game_id, player_name=winner, event_type=event_type.value))
            db.commit()

    def finish_game(self, game_id: int) -> None:
        with self._session_factory() as db:
            game = db.get(Game, game_id)
            if game is None:
                raise ValueError("game not found")
            game.status = "finished"
            game.finished_at = datetime.now(timezone.utc)
            db.commit()

    def save_result(self, game_id: int, net: dict[str, int]) -> None:
        game = self.get_game(game_id)
        if game is None:
            raise ValueError("game not found")

        with self._session_factory() as db:
            db.query(GameResult).filter(GameResult.game_id == game_id).delete(synchronize_session=False)
            db.add_all(
                [
                    GameResult(
                        game_id=game_id,
                        player_name=player,
                        net=float(amount),
                        card_closed=player in game.card_winners,
                    )
                    for player, amount in net.items()
                ]
            )

            players = db.scalars(select(GamePlayer).where(GamePlayer.game_id == game_id)).all()
            for player in players:
                amount = float(net.get(player.player_name, 0))
                player.payout = player.buy_in + amount
                player.card_closed = player.player_name in game.card_winners

            db.commit()

    def get_result(self, game_id: int) -> dict[str, int]:
        with self._session_factory() as db:
            rows = db.scalars(select(GameResult).where(GameResult.game_id == game_id).order_by(GameResult.player_name)).all()
            return {row.player_name: int(row.net) for row in rows}

    def get_global_balance(self) -> dict[str, int]:
        with self._session_factory() as db:
            rows = db.execute(
                select(GameResult.player_name, func.coalesce(func.sum(GameResult.net), 0.0).label("total"))
                .join(Game, Game.id == GameResult.game_id)
                .where(Game.status == "finished")
                .group_by(GameResult.player_name)
                .order_by(GameResult.player_name)
            ).all()
            return {row.player_name: int(row.total) for row in rows}

    def get_games_count(self) -> int:
        with self._session_factory() as db:
            row = db.execute(select(func.count(Game.id)).where(Game.status == "finished")).one()
            return int(row[0] or 0)

    def get_player_stats(self, name: str) -> dict[str, object]:
        with self._session_factory() as db:
            history_rows = db.execute(
                select(GameResult.game_id, Game.finished_at, GameResult.net, GameResult.card_closed)
                .join(Game, Game.id == GameResult.game_id)
                .where(Game.status == "finished", GameResult.player_name == name)
                .order_by(Game.finished_at.desc().nullslast(), GameResult.game_id.desc())
            ).all()

            totals = db.execute(
                select(
                    func.coalesce(func.sum(GameResult.net), 0.0),
                    func.count(GameResult.id),
                    func.coalesce(func.sum(case((GameResult.card_closed.is_(True), 1), else_=0)), 0),
                )
                .join(Game, Game.id == GameResult.game_id)
                .where(Game.status == "finished", GameResult.player_name == name)
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
                        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
                        "net": float(row.net),
                        "card_closed": row.card_closed,
                    }
                    for row in history_rows
                ],
            }
