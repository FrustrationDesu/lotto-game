from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class GameEventType(str, Enum):
    LINE_CLOSED = "line_closed"
    CARD_CLOSED = "card_closed"


class DomainValidationError(ValueError):
    """Raised when a game rule is violated."""


@dataclass(slots=True, frozen=True)
class GameSettings:
    card_price_kopecks: int
    line_bonus_kopecks: int

    def __post_init__(self) -> None:
        if self.card_price_kopecks <= 0:
            raise DomainValidationError("card_price_kopecks must be positive")
        if self.line_bonus_kopecks <= 0:
            raise DomainValidationError("line_bonus_kopecks must be positive")


@dataclass(slots=True, frozen=True)
class GameEvent:
    type: GameEventType
    players: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.players:
            raise DomainValidationError("event must have at least one player")


def normalize_player(name: str) -> str:
    value = name.strip()
    if not value:
        raise DomainValidationError("player name must be non-empty")
    return value


def unique_preserve_order(players: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for p in players:
        np = normalize_player(p)
        if np not in seen:
            seen.add(np)
            result.append(np)
    return result


def calculate_net(
    players: list[str],
    settings: GameSettings,
    line_winners: list[str],
    card_winners: list[str],
) -> dict[str, int]:
    if len(players) < 2:
        raise DomainValidationError("at least 2 players required")
    if not card_winners:
        raise DomainValidationError("at least one card winner required")

    net = {player: -settings.card_price_kopecks for player in players}
    total_players = len(players)

    for winner in line_winners:
        if winner not in net:
            raise DomainValidationError(f"unknown line winner: {winner}")
        for player in players:
            if player == winner:
                continue
            net[player] -= settings.line_bonus_kopecks
        net[winner] += settings.line_bonus_kopecks * (total_players - 1)

    pot = settings.card_price_kopecks * total_players
    ordered_winners = unique_preserve_order(card_winners)
    if len(ordered_winners) != len(card_winners):
        raise DomainValidationError("card winners must be unique")

    share, remainder = divmod(pot, len(ordered_winners))
    for idx, winner in enumerate(ordered_winners):
        if winner not in net:
            raise DomainValidationError(f"unknown card winner: {winner}")
        net[winner] += share + (1 if idx < remainder else 0)

    return net


def build_transfers(net: dict[str, int]) -> list[dict[str, int | str]]:
    creditors = [(name, amount) for name, amount in net.items() if amount > 0]
    debtors = [(name, -amount) for name, amount in net.items() if amount < 0]

    transfers: list[dict[str, int | str]] = []
    c_idx = d_idx = 0
    while c_idx < len(creditors) and d_idx < len(debtors):
        c_name, c_amount = creditors[c_idx]
        d_name, d_amount = debtors[d_idx]
        amount = min(c_amount, d_amount)
        transfers.append({"from": d_name, "to": c_name, "amount_kopecks": amount})

        c_amount -= amount
        d_amount -= amount
        creditors[c_idx] = (c_name, c_amount)
        debtors[d_idx] = (d_name, d_amount)
        if c_amount == 0:
            c_idx += 1
        if d_amount == 0:
            d_idx += 1

    return transfers
