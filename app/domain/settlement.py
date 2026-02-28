"""Domain logic for player settlement in the lotto game."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN


@dataclass
class SettlementResult:
    payouts: dict[str, Decimal]


def settle(bank: Decimal, line_winners: Sequence[str], card_winners: Sequence[str]) -> SettlementResult:
    winners = _deduplicate_preserve_order([*line_winners, *card_winners])
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


def calculate_settlement(
    players: Sequence[str],
    card_price: int,
    line_bonus: int,
    line_winner: str,
    card_winners: Sequence[str],
) -> dict:
    if not players:
        raise ValueError("players must not be empty")
    if card_price < 0 or line_bonus < 0:
        raise ValueError("card_price and line_bonus must be non-negative")
    if line_winner not in players:
        raise ValueError("line_winner must be one of players")
    if not card_winners:
        raise ValueError("card_winners must not be empty")

    players_unique = _deduplicate_preserve_order(players)
    if len(players_unique) != len(players):
        raise ValueError("players must contain unique ids")

    card_winners_unique = _deduplicate_preserve_order(card_winners)
    card_winners_set = set(card_winners_unique)
    unknown_winners = card_winners_set.difference(players_unique)
    if unknown_winners:
        raise ValueError("all card_winners must be in players")

    player_count = len(players_unique)
    pot = player_count * card_price

    net_by_player = {player: -card_price for player in players_unique}

    for player in players_unique:
        if player != line_winner:
            net_by_player[player] -= line_bonus
    line_payouts_total = (player_count - 1) * line_bonus
    net_by_player[line_winner] += line_payouts_total

    share, remainder = divmod(pot, len(card_winners_unique))
    for winner in card_winners_unique:
        net_by_player[winner] += share

    if remainder:
        distributed = 0
        for player in players_unique:
            if player in card_winners_set:
                net_by_player[player] += 1
                distributed += 1
                if distributed == remainder:
                    break

    transfers = calculate_transfers(net_by_player)

    return {
        "net_by_player": net_by_player,
        "transfers": transfers,
        "pot": pot,
        "line_payouts_total": line_payouts_total,
    }


def calculate_transfers(net_by_player: Mapping[str, int]) -> list[dict[str, int | str]]:
    debtors = sorted(
        ((player, -amount) for player, amount in net_by_player.items() if amount < 0),
        key=lambda item: item[0],
    )
    creditors = sorted(
        ((player, amount) for player, amount in net_by_player.items() if amount > 0),
        key=lambda item: item[0],
    )

    transfers: list[dict[str, int | str]] = []
    debtor_idx = 0
    creditor_idx = 0

    while debtor_idx < len(debtors) and creditor_idx < len(creditors):
        debtor, debt_left = debtors[debtor_idx]
        creditor, credit_left = creditors[creditor_idx]

        amount = debt_left if debt_left <= credit_left else credit_left
        transfers.append({"from": debtor, "to": creditor, "amount": amount})

        debt_left -= amount
        credit_left -= amount

        debtors[debtor_idx] = (debtor, debt_left)
        creditors[creditor_idx] = (creditor, credit_left)

        if debt_left == 0:
            debtor_idx += 1
        if credit_left == 0:
            creditor_idx += 1

    if debtor_idx != len(debtors) or creditor_idx != len(creditors):
        raise ValueError("invalid net state: debts and credits are imbalanced")

    return transfers


def _deduplicate_preserve_order(items: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
