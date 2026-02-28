"""Domain logic for settlements and transfer calculation in the lotto game."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN

from .game import DomainValidationError, GameSettings, unique_preserve_order


@dataclass
class SettlementResult:
    payouts: dict[str, Decimal]


def settle(bank: Decimal, line_winners: Sequence[str], card_winners: Sequence[str]) -> SettlementResult:
    winners = unique_preserve_order([*line_winners, *card_winners])
    if not winners:
        return SettlementResult(payouts={})

    cents = int((bank * 100).to_integral_value(rounding=ROUND_DOWN))
    share, remainder = divmod(cents, len(winners))

    payouts: dict[str, Decimal] = {}
    for idx, winner in enumerate(winners):
        amount_cents = share + (1 if idx < remainder else 0)
        payouts[winner] = (Decimal(amount_cents) / Decimal(100)).quantize(Decimal("0.01"))

    return SettlementResult(payouts=payouts)


def settle_game(bank: Decimal, line_winners: Sequence[str], card_winners: Sequence[str]) -> SettlementResult:
    return settle(bank=bank, line_winners=line_winners, card_winners=card_winners)


def calculate_net(
    players: list[str],
    settings: GameSettings,
    line_winners: list[str],
    card_winners: list[str],
) -> dict[str, int]:
    ordered_players = unique_preserve_order(players)
    if len(ordered_players) < 2:
        raise DomainValidationError("at least 2 players required")
    if len(ordered_players) != len(players):
        raise DomainValidationError("players must be unique")
    if not card_winners:
        raise DomainValidationError("at least one card winner required")

    net = {player: -settings.card_price_kopecks for player in ordered_players}
    total_players = len(ordered_players)

    for winner in line_winners:
        if winner not in net:
            raise DomainValidationError(f"unknown line winner: {winner}")
        for player in ordered_players:
            if player != winner:
                net[player] -= settings.line_bonus_kopecks
        net[winner] += settings.line_bonus_kopecks * (total_players - 1)

    ordered_winners = unique_preserve_order(card_winners)
    if len(ordered_winners) != len(card_winners):
        raise DomainValidationError("card winners must be unique")

    pot = settings.card_price_kopecks * total_players
    share, remainder = divmod(pot, len(ordered_winners))
    for idx, winner in enumerate(ordered_winners):
        if winner not in net:
            raise DomainValidationError(f"unknown card winner: {winner}")
        net[winner] += share + (1 if idx < remainder else 0)

    return net


def build_transfers(net: Mapping[str, int]) -> list[dict[str, int | str]]:
    creditors = [(name, amount) for name, amount in net.items() if amount > 0]
    debtors = [(name, -amount) for name, amount in net.items() if amount < 0]

    transfers: list[dict[str, int | str]] = []
    creditor_idx = 0
    debtor_idx = 0
    while creditor_idx < len(creditors) and debtor_idx < len(debtors):
        creditor_name, creditor_amount = creditors[creditor_idx]
        debtor_name, debtor_amount = debtors[debtor_idx]

        amount = min(creditor_amount, debtor_amount)
        transfers.append({"from": debtor_name, "to": creditor_name, "amount_kopecks": amount})

        creditor_amount -= amount
        debtor_amount -= amount
        creditors[creditor_idx] = (creditor_name, creditor_amount)
        debtors[debtor_idx] = (debtor_name, debtor_amount)

        if creditor_amount == 0:
            creditor_idx += 1
        if debtor_amount == 0:
            debtor_idx += 1

    return transfers


def calculate_settlement(
    players: Sequence[str],
    card_price: int,
    line_bonus: int,
    line_winner: str,
    card_winners: Sequence[str],
) -> dict:
    settings = GameSettings(card_price_kopecks=card_price, line_bonus_kopecks=line_bonus)
    net_by_player = calculate_net(
        players=list(players),
        settings=settings,
        line_winners=[line_winner],
        card_winners=list(card_winners),
    )
    return {
        "net_by_player": net_by_player,
        "transfers": build_transfers(net_by_player),
        "pot": len(players) * card_price,
        "line_payouts_total": (len(players) - 1) * line_bonus,
    }


def calculate_transfers(net_by_player: Mapping[str, int]) -> list[dict[str, int | str]]:
    """Backward-compatible alias."""
    return build_transfers(net_by_player)
