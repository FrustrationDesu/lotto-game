from app.domain import GameSettings, build_transfers, calculate_net


def test_split_pot_between_two_winners_and_single_line_each_player_once() -> None:
    players = ["Альберт", "Паша", "Лена", "Оля"]
    settings = GameSettings(card_price_kopecks=1000, line_bonus_kopecks=500)

    net = calculate_net(
        players=players,
        settings=settings,
        line_winners=["Альберт", "Паша"],
        card_winners=["Альберт", "Паша"],
    )

    assert sum(net.values()) == 0
    assert net["Альберт"] == 2000
    assert net["Паша"] == 2000
    assert net["Лена"] == -2000
    assert net["Оля"] == -2000

    transfers = build_transfers(net)
    assert sum(t["amount_kopecks"] for t in transfers) == 4000


def test_remainder_distribution_is_deterministic() -> None:
    players = ["A", "B", "C"]
    settings = GameSettings(card_price_kopecks=101, line_bonus_kopecks=10)

    net = calculate_net(players, settings, line_winners=[], card_winners=["A", "B"])

    assert net == {"A": 51, "B": 50, "C": -101}
