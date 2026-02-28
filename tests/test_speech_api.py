import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_speech_interpret_success_contract() -> None:
    response = client.post(
        "/speech/interpret",
        json={
            "text": "Закрыл линию паша",
            "players": ["Паша", "Лена"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "raw_text",
        "normalized_text",
        "intent",
        "confidence",
        "player_id",
        "event_endpoint",
        "errors",
    }
    assert body["intent"] == "close_line"
    assert body["player_id"] == "Паша"
    assert body["errors"] == []


def test_speech_interpret_error_contract() -> None:
    response = client.post(
        "/speech/interpret",
        json={
            "text": "произвольный текст",
            "players": ["Паша"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "raw_text",
        "normalized_text",
        "intent",
        "confidence",
        "player_id",
        "event_endpoint",
        "errors",
    }
    assert body["intent"] == "unknown"
    assert body["confidence"] is None
    assert body["player_id"] is None
    assert body["errors"]
