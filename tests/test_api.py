import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from app.main import app
from app.services.transcription_service import TranscriptionProviderError, TranscriptionResult


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


def test_transcribe_success(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_transcribe_audio(*, filename: str, content_type: str, data: bytes) -> TranscriptionResult:
        assert filename == "voice.webm"
        assert content_type == "audio/webm"
        assert data == b"abc"
        return TranscriptionResult(
            text="привет",
            language="ru",
            duration_seconds=1.25,
            provider="openai",
        )

    monkeypatch.setattr("app.main.transcribe_audio", fake_transcribe_audio)

    response = client.post(
        "/speech/transcribe",
        files={"file": ("voice.webm", b"abc", "audio/webm")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "text": "привет",
        "language": "ru",
        "duration_seconds": 1.25,
        "provider": "openai",
    }


def test_transcribe_unsupported_mime_type() -> None:
    response = client.post(
        "/speech/transcribe",
        files={"file": ("voice.ogg", b"abc", "audio/ogg")},
    )

    assert response.status_code == 400
    assert "Unsupported MIME type" in response.json()["detail"]


def test_transcribe_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_transcribe_audio(*, filename: str, content_type: str, data: bytes) -> TranscriptionResult:
        raise TranscriptionProviderError("upstream rate limit", status_code=502)

    monkeypatch.setattr("app.main.transcribe_audio", fake_transcribe_audio)

    response = client.post(
        "/speech/transcribe",
        files={"file": ("voice.webm", b"abc", "audio/webm")},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "upstream rate limit"
