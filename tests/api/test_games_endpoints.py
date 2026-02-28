import importlib

import pytest
from fastapi.testclient import TestClient



def _import_any(*candidates: str):
    for name in candidates:
        try:
            return importlib.import_module(name)
        except ModuleNotFoundError:
            continue
    pytest.fail(f"Не удалось импортировать ни один модуль из: {candidates}")


api_module = _import_any("lotto_game.api.main", "api.main", "app.main", "main")
app = getattr(api_module, "app", None)
if app is None:
    pytest.fail("Не найден FastAPI app")


@pytest.fixture
def client():
    return TestClient(app)


def test_happy_path_full_game_cycle(client: TestClient):
    create_resp = client.post("/games")
    assert create_resp.status_code in (200, 201), create_resp.text
    game_id = create_resp.json().get("id")
    assert game_id

    join_1 = client.post(f"/games/{game_id}/players", json={"player_id": "p1", "stake": 10})
    assert join_1.status_code in (200, 201), join_1.text

    join_2 = client.post(f"/games/{game_id}/players", json={"player_id": "p2", "stake": 5})
    assert join_2.status_code in (200, 201), join_2.text

    start_resp = client.post(f"/games/{game_id}/start")
    assert start_resp.status_code in (200, 202), start_resp.text

    line_resp = client.post(f"/games/{game_id}/line", json={"player_id": "p1"})
    assert line_resp.status_code in (200, 201), line_resp.text

    card_resp = client.post(f"/games/{game_id}/card", json={"player_id": "p2"})
    assert card_resp.status_code in (200, 201), card_resp.text

    finish_resp = client.post(f"/games/{game_id}/finish")
    assert finish_resp.status_code in (200, 201), finish_resp.text

    get_resp = client.get(f"/games/{game_id}")
    assert get_resp.status_code == 200, get_resp.text
    payload = get_resp.json()
    assert payload.get("id") == game_id
    assert payload.get("status") in ("finished", "completed")


def test_domain_error_same_player_reports_line_twice(client: TestClient):
    create_resp = client.post("/games")
    game_id = create_resp.json()["id"]

    client.post(f"/games/{game_id}/players", json={"player_id": "p1", "stake": 10})
    client.post(f"/games/{game_id}/players", json={"player_id": "p2", "stake": 5})
    client.post(f"/games/{game_id}/start")

    first_line = client.post(f"/games/{game_id}/line", json={"player_id": "p1"})
    assert first_line.status_code in (200, 201), first_line.text

    second_line = client.post(f"/games/{game_id}/line", json={"player_id": "p1"})
    assert second_line.status_code in (400, 409, 422), second_line.text
