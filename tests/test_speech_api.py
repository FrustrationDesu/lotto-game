import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_transcribe_success_contract() -> None:
    response = client.post(
        "/speech/transcribe",
        files={"file": ("recording.webm", b"fake-audio-data", "audio/webm")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["text"]
    assert body["language"] == "ru"
    assert body["provider"] == "mock-media-recorder"


def test_transcribe_empty_payload() -> None:
    response = client.post(
        "/speech/transcribe",
        files={"file": ("recording.webm", b"", "audio/webm")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Empty audio payload"
