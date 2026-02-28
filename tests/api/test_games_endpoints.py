import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_create_line_card_finish_settlement_contract(client: TestClient) -> None:
    create = client.post(
        "/games",
        json={
            "players": ["alice", "bob", "charlie"],
            "card_price_kopecks": 1000,
            "line_bonus_kopecks": 500,
        },
    )
    assert create.status_code == 200
    create_json = create.json()
    assert set(create_json.keys()) == {"game_id"}
    game_id = create_json["game_id"]

    line = client.post(f"/games/{game_id}/events/line", json={"players": ["alice"]})
    assert line.status_code == 200
    assert line.json() == {"status": "ok"}

    card = client.post(f"/games/{game_id}/events/card", json={"players": ["bob"]})
    assert card.status_code == 200
    assert card.json() == {"status": "ok"}

    finish = client.post(f"/games/{game_id}/finish")
    assert finish.status_code == 200
    finish_json = finish.json()
    assert set(finish_json.keys()) == {"game_id", "net", "transfers"}

    settlement = client.get(f"/games/{game_id}/settlement")
    assert settlement.status_code == 200
    assert set(settlement.json().keys()) == {"game_id", "net", "transfers"}


def test_game_domain_error_shape(client: TestClient) -> None:
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
    duplicate_line = client.post(f"/games/{game_id}/events/line", json={"players": ["alice"]})

    assert duplicate_line.status_code == 400
    error_json = duplicate_line.json()
    assert set(error_json.keys()) == {"detail"}
    assert isinstance(error_json["detail"], str)


def test_session_contract_includes_ruble_mirrors(client: TestClient) -> None:
    create = client.post(
        "/sessions",
        json={
            "players": ["alice", "bob", "charlie"],
            "card_price_kopecks": 1000,
            "line_bonus_kopecks": 500,
        },
    )
    assert create.status_code == 200
    create_json = create.json()
    assert create_json["card_price_rub"] == 10.0
    assert create_json["line_bonus_rub"] == 5.0

    session_id = create_json["session_id"]
    client.post(f"/sessions/{session_id}/line", json={"players": ["alice"]})
    client.post(f"/sessions/{session_id}/card", json={"players": ["bob"]})

    finish = client.post(f"/sessions/{session_id}/finish")
    assert finish.status_code == 200
    finish_json = finish.json()
    assert set(finish_json.keys()) == {
        "game_number",
        "line_winners",
        "card_winners",
        "net",
        "transfers",
        "net_rub",
        "transfers_rub",
        "finished_at",
    }

    session = client.get(f"/sessions/{session_id}")
    assert session.status_code == 200
    session_json = session.json()
    assert session_json["card_price_rub"] == 10.0
    assert session_json["line_bonus_rub"] == 5.0
    assert "net_rub" in session_json["history"][0]
    assert "transfers_rub" in session_json["history"][0]
