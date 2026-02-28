import importlib
from decimal import Decimal

import pytest



def _import_any(*candidates: str):
    for name in candidates:
        try:
            return importlib.import_module(name)
        except ModuleNotFoundError:
            continue
    pytest.fail(f"Не удалось импортировать ни один модуль из: {candidates}")


settlement_module = _import_any("lotto_game.domain.settlement", "domain.settlement", "app.domain.settlement")


settle = getattr(settlement_module, "settle", None) or getattr(settlement_module, "settle_game", None)
if settle is None:
    pytest.fail("В модуле settlement не найдена функция settle/settle_game")


@pytest.mark.parametrize(
    "line_winners, card_winners, expected_each",
    [
        (["p1"], [], {"p1": Decimal("100.00")}),
        (["p1", "p2"], [], {"p1": Decimal("50.00"), "p2": Decimal("50.00")}),
        ([], ["p1", "p2"], {"p1": Decimal("50.00"), "p2": Decimal("50.00")}),
    ],
    ids=["one_line_winner", "two_line_winners", "two_card_winners"],
)
def test_settlement_winners_split(line_winners, card_winners, expected_each):
    result = settle(
        bank=Decimal("100.00"),
        line_winners=line_winners,
        card_winners=card_winners,
    )

    payouts = getattr(result, "payouts", result)
    assert payouts == expected_each


def test_settlement_handles_kopeck_non_divisible_bank():
    """
    Регрессия для кейса семьи из примера: вклад 10 и 5 рублей.
    Общий банк 15.00 делится между двумя победителями с сохранением копеек.
    """
    result = settle(
        bank=Decimal("15.00"),
        line_winners=["family_10", "family_5"],
        card_winners=[],
    )
    payouts = getattr(result, "payouts", result)

    assert sum(payouts.values()) == Decimal("15.00")
    assert set(payouts) == {"family_10", "family_5"}
    assert sorted(payouts.values()) == [Decimal("7.50"), Decimal("7.50")]
