from __future__ import annotations

from app.domain import (
    DomainValidationError,
    GameEvent,
    GameEventType,
    GameSettings,
    build_transfers,
    calculate_net,
    unique_preserve_order,
)
from app.repository import LottoRepository


class LottoService:
    def __init__(self, repo: LottoRepository) -> None:
        self.repo = repo

    def start_game(self, players: list[str], card_price_kopecks: int, line_bonus_kopecks: int) -> int:
        normalized = unique_preserve_order(players)
        if len(normalized) < 2:
            raise DomainValidationError("at least 2 unique players required")
        GameSettings(card_price_kopecks=card_price_kopecks, line_bonus_kopecks=line_bonus_kopecks)
        return self.repo.create_game(normalized, card_price_kopecks, line_bonus_kopecks)

    def add_event(self, game_id: int, event: GameEvent) -> None:
        game = self.repo.get_game(game_id)
        if game is None:
            raise DomainValidationError("game not found")
        if game.finished_at is not None:
            raise DomainValidationError("game already finished")

        winners = unique_preserve_order(event.player_ids)
        for winner in winners:
            if winner not in game.players:
                raise DomainValidationError(f"unknown player: {winner}")

        if event.event_type == GameEventType.LINE_CLOSED:
            duplicates = set(winners) & set(game.line_winners)
            if duplicates:
                raise DomainValidationError(
                    f"line already closed by: {', '.join(sorted(duplicates))}"
                )
        else:
            duplicates = set(winners) & set(game.card_winners)
            if duplicates:
                raise DomainValidationError(
                    f"card already closed by: {', '.join(sorted(duplicates))}"
                )

        self.repo.append_winners(game_id, event.event_type, winners)

    def finish_game(self, game_id: int) -> dict[str, object]:
        game = self.repo.get_game(game_id)
        if game is None:
            raise DomainValidationError("game not found")
        if game.finished_at is not None:
            raise DomainValidationError("game already finished")

        settings = GameSettings(
            card_price_kopecks=game.card_price_kopecks,
            line_bonus_kopecks=game.line_bonus_kopecks,
        )
        net = calculate_net(
            players=game.players,
            settings=settings,
            line_winners=game.line_winners,
            card_winners=game.card_winners,
        )

        self.repo.finish_game(game_id)
        self.repo.save_result(game_id, net)
        return {
            "game_id": game_id,
            "net": net,
            "transfers": build_transfers(net),
        }

    def get_settlement(self, game_id: int) -> dict[str, object]:
        game = self.repo.get_game(game_id)
        if game is None:
            raise DomainValidationError("game not found")
        result = self.repo.get_result(game_id)
        if not result:
            raise DomainValidationError("game is not finished")
        return {"game_id": game_id, "net": result, "transfers": build_transfers(result)}

    def get_stats(self) -> dict[str, object]:
        return {
            "games_finished": self.repo.get_games_count(),
            "global_balance": self.repo.get_global_balance(),
        }
