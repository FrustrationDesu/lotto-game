import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_speech_interpret_success() -> None:
    response = client.post(
        "/speech/interpret",
        json={
            "text": "Закрыл линию паша",
            "players": ["Паша", "Лена"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["raw_text"] == "Закрыл линию паша"
    assert body["normalized_text"] == "закрыл линию паша"
    assert body["intent"] == "close_line"
    assert body["player_id"] == "Паша"
    assert body["event_endpoint"] == "/games/{game_id}/events/line"
    assert body["errors"] == []


def test_speech_interpret_returns_traceable_error_fields() -> None:
    response = client.post(
        "/speech/interpret",
        json={
            "text": "произвольный текст",
            "players": ["Паша"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["raw_text"] == "произвольный текст"
    assert body["normalized_text"] == "произвольный текст"
    assert body["intent"] == "unknown"
    assert body["confidence"] is None
    assert body["errors"]
