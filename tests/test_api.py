import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_game_flow_and_stats() -> None:
    start = client.post(
        "/games",
        json={
            "players": ["Альберт", "Паша", "Лена"],
            "card_price_kopecks": 1000,
            "line_bonus_kopecks": 500,
        },
    )
    assert start.status_code == 200
    game_id = start.json()["game_id"]

    line = client.post(f"/games/{game_id}/events/line", json={"players": ["Альберт", "Паша"]})
    assert line.status_code == 200

    duplicate_line = client.post(f"/games/{game_id}/events/line", json={"players": ["Альберт"]})
    assert duplicate_line.status_code == 400

    card = client.post(f"/games/{game_id}/events/card", json={"players": ["Паша"]})
    assert card.status_code == 200

    finish = client.post(f"/games/{game_id}/finish")
    assert finish.status_code == 200
    body = finish.json()
    assert body["net"]["Паша"] == 3000
    assert body["net"]["Лена"] == -2000

    stats = client.get("/stats/balance")
    assert stats.status_code == 200
    assert stats.json()["games_finished"] >= 1
    assert stats.json()["global_balance"]["Паша"] >= 3000
