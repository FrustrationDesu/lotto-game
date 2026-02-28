import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_stats_contract_after_finished_game() -> None:
    create = client.post(
        "/games",
        json={
            "players": ["alice", "bob"],
            "card_price_kopecks": 1000,
            "line_bonus_kopecks": 500,
        },
    )
    game_id = create.json()["game_id"]

    client.post(f"/games/{game_id}/events/line", json={"players": ["alice"]})
    client.post(f"/games/{game_id}/events/card", json={"players": ["bob"]})
    client.post(f"/games/{game_id}/finish")

    response = client.get("/stats/balance")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {"games_finished", "global_balance"}
    assert payload["games_finished"] >= 1
    assert set(payload["global_balance"].keys()) >= {"alice", "bob"}
