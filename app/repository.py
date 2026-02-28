from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from app.domain import GameEventType


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
    def __init__(self, db_path: str = "lotto.db") -> None:
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                players_json TEXT NOT NULL,
                card_price_kopecks INTEGER NOT NULL,
                line_bonus_kopecks INTEGER NOT NULL,
                line_winners_json TEXT NOT NULL DEFAULT '[]',
                card_winners_json TEXT NOT NULL DEFAULT '[]',
                finished_at TEXT
            );
            CREATE TABLE IF NOT EXISTS game_results (
                game_id INTEGER NOT NULL,
                player TEXT NOT NULL,
                net_kopecks INTEGER NOT NULL,
                PRIMARY KEY (game_id, player)
            );
            """
        )
        self.conn.commit()

    def create_game(self, players: list[str], card_price_kopecks: int, line_bonus_kopecks: int) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO games(players_json, card_price_kopecks, line_bonus_kopecks)
            VALUES (?, ?, ?)
            """,
            (json.dumps(players, ensure_ascii=False), card_price_kopecks, line_bonus_kopecks),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_game(self, game_id: int) -> GameRow | None:
        row = self.conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
        if row is None:
            return None
        return GameRow(
            id=row["id"],
            players=json.loads(row["players_json"]),
            card_price_kopecks=row["card_price_kopecks"],
            line_bonus_kopecks=row["line_bonus_kopecks"],
            line_winners=json.loads(row["line_winners_json"]),
            card_winners=json.loads(row["card_winners_json"]),
            finished_at=row["finished_at"],
        )

    def append_winners(self, game_id: int, event_type: GameEventType, winners: list[str]) -> None:
        game = self.get_game(game_id)
        if game is None:
            raise ValueError("game not found")
        if event_type == GameEventType.LINE_CLOSED:
            updated = game.line_winners + winners
            field = "line_winners_json"
        else:
            updated = game.card_winners + winners
            field = "card_winners_json"

        self.conn.execute(
            f"UPDATE games SET {field} = ? WHERE id = ?",
            (json.dumps(updated, ensure_ascii=False), game_id),
        )
        self.conn.commit()

    def finish_game(self, game_id: int) -> None:
        finished_at = datetime.now(timezone.utc).isoformat()
        self.conn.execute("UPDATE games SET finished_at = ? WHERE id = ?", (finished_at, game_id))
        self.conn.commit()

    def save_result(self, game_id: int, net: dict[str, int]) -> None:
        self.conn.execute("DELETE FROM game_results WHERE game_id = ?", (game_id,))
        self.conn.executemany(
            "INSERT INTO game_results(game_id, player, net_kopecks) VALUES (?, ?, ?)",
            [(game_id, player, amount) for player, amount in net.items()],
        )
        self.conn.commit()

    def get_result(self, game_id: int) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT player, net_kopecks FROM game_results WHERE game_id = ? ORDER BY player", (game_id,)
        ).fetchall()
        return {row["player"]: row["net_kopecks"] for row in rows}

    def get_global_balance(self) -> dict[str, int]:
        rows = self.conn.execute(
            """
            SELECT player, SUM(net_kopecks) AS total
            FROM game_results
            GROUP BY player
            ORDER BY player
            """
        ).fetchall()
        return {row["player"]: int(row["total"]) for row in rows}

    def get_games_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS c FROM games WHERE finished_at IS NOT NULL").fetchone()
        return int(row["c"])
