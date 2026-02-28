import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_smoke_game_lifecycle_stats_and_speech_interpret() -> None:
    create = client.post(
        "/games",
        json={
            "players": ["Альберт", "Паша", "Лена"],
            "card_price_kopecks": 1000,
            "line_bonus_kopecks": 500,
        },
    )
    assert create.status_code == 200
    create_json = create.json()
    assert set(create_json.keys()) == {"game_id"}
    game_id = create_json["game_id"]

    line = client.post(f"/games/{game_id}/events/line", json={"players": ["Паша"]})
    assert line.status_code == 200
    assert line.json() == {"status": "ok"}

    card = client.post(f"/games/{game_id}/events/card", json={"players": ["Лена"]})
    assert card.status_code == 200
    assert card.json() == {"status": "ok"}

    finish = client.post(f"/games/{game_id}/finish")
    assert finish.status_code == 200
    finish_json = finish.json()
    assert set(finish_json.keys()) == {"game_id", "net", "transfers"}

    settlement = client.get(f"/games/{game_id}/settlement")
    assert settlement.status_code == 200
    settlement_json = settlement.json()
    assert set(settlement_json.keys()) == {"game_id", "net", "transfers"}

    stats = client.get("/stats/balance")
    assert stats.status_code == 200
    stats_json = stats.json()
    assert set(stats_json.keys()) == {"games_finished", "global_balance"}
    assert stats_json["games_finished"] >= 1

    speech = client.post(
        "/speech/interpret",
        json={"text": "Закрыл линию паша", "players": ["Альберт", "Паша", "Лена"]},
    )
    assert speech.status_code == 200
    speech_json = speech.json()
    assert set(speech_json.keys()) == {
        "raw_text",
        "normalized_text",
        "intent",
        "confidence",
        "player_id",
        "event_endpoint",
        "errors",
    }
    assert speech_json["intent"] == "close_line"
    assert speech_json["player_id"] == "Паша"
    assert speech_json["event_endpoint"] == "/games/{game_id}/events/line"
    assert speech_json["errors"] == []


def test_duplicate_line_event_returns_consistent_error_shape() -> None:
    create = client.post(
        "/games",
        json={
            "players": ["Альберт", "Паша"],
            "card_price_kopecks": 1000,
            "line_bonus_kopecks": 500,
        },
    )
    game_id = create.json()["game_id"]

    first_line = client.post(f"/games/{game_id}/events/line", json={"players": ["Паша"]})
    assert first_line.status_code == 200

    duplicate_line = client.post(f"/games/{game_id}/events/line", json={"players": ["Паша"]})
    assert duplicate_line.status_code == 400
    error_json = duplicate_line.json()
    assert set(error_json.keys()) == {"detail"}
    assert isinstance(error_json["detail"], str)


def test_session_endpoints_return_ruble_fields_and_convert_values() -> None:
    create = client.post(
        "/sessions",
        json={
            "players": ["Альберт", "Паша", "Лена"],
            "card_price_kopecks": 1234,
            "line_bonus_kopecks": 567,
        },
    )
    assert create.status_code == 200
    create_json = create.json()
    assert create_json["card_price_kopecks"] == 1234
    assert create_json["line_bonus_kopecks"] == 567
    assert create_json["card_price_rub"] == 12.34
    assert create_json["line_bonus_rub"] == 5.67

    session_id = create_json["session_id"]
    line = client.post(f"/sessions/{session_id}/line", json={"players": ["Паша"]})
    assert line.status_code == 200

    card = client.post(f"/sessions/{session_id}/card", json={"players": ["Лена"]})
    assert card.status_code == 200

    finish = client.post(f"/sessions/{session_id}/finish")
    assert finish.status_code == 200
    finish_json = finish.json()
    assert "net" in finish_json
    assert "transfers" in finish_json
    assert "net_rub" in finish_json
    assert "transfers_rub" in finish_json
    assert finish_json["net_rub"]["Альберт"] == finish_json["net"]["Альберт"] / 100

    for transfer, transfer_rub in zip(finish_json["transfers"], finish_json["transfers_rub"], strict=True):
        assert transfer_rub["from"] == transfer["from"]
        assert transfer_rub["to"] == transfer["to"]
        assert transfer_rub["amount_rub"] == transfer["amount_kopecks"] / 100

    session = client.get(f"/sessions/{session_id}")
    assert session.status_code == 200
    session_json = session.json()
    assert session_json["card_price_rub"] == 12.34
    assert session_json["line_bonus_rub"] == 5.67
    history_entry = session_json["history"][0]
    assert "net_rub" in history_entry
    assert "transfers_rub" in history_entry
