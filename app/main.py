from __future__ import annotations

from datetime import datetime
from itertools import count
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.games import router as games_router
from app.api.speech import router as speech_router
from app.api.stats import router as stats_router
from app.domain import GameSettings, build_transfers, calculate_net


class SessionCreateRequest(BaseModel):
    players: list[str] = Field(min_length=2)
    card_price_kopecks: int = Field(gt=0)
    line_bonus_kopecks: int = Field(gt=0)


class SessionWinnersRequest(BaseModel):
    players: list[str] = Field(min_length=1)


app = FastAPI(title="Lotto Game API")
app.include_router(games_router)
app.include_router(stats_router)
app.include_router(speech_router)

session_counter = count(1)
SESSIONS: dict[int, dict[str, Any]] = {}


@app.get("/", response_class=HTMLResponse)
def frontend() -> str:
    return """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <title>Lotto Session</title>
  <style>
    body { font-family: sans-serif; max-width: 860px; margin: 2rem auto; }
    .card { border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }
    .hidden { display:none; }
    .winners label { margin-right: 1rem; display: inline-block; }
    button { padding: 0.4rem 0.8rem; }
    pre { background: #f7f7f7; padding: 0.8rem; white-space: pre-wrap; }
  </style>
</head>
<body>
  <h1>Lotto: сессия игр</h1>

  <div class="card">
    <h2>Создать сессию</h2>
    <form id="createSessionForm">
      <label>Игроки (через запятую): <input id="players" required value="Альберт,Паша,Лена" /></label><br/><br/>
      <label>Цена карточки (коп): <input id="cardPrice" type="number" min="1" required value="1000" /></label><br/><br/>
      <label>Бонус за линию (коп): <input id="lineBonus" type="number" min="1" required value="500" /></label><br/><br/>
      <button type="submit">Создать сессию</button>
    </form>
    <p id="sessionInfo"></p>
  </div>

  <div id="gameFlow" class="card hidden">
    <h2 id="question">Кто закрыл линию?</h2>
    <div id="winners" class="winners"></div>
    <button id="confirmStep">Подтвердить</button>
    <button id="newGame">Новая игра в сессии</button>
  </div>

  <div class="card">
    <h2>История сессии</h2>
    <pre id="history">Сессия еще не создана</pre>
  </div>

<script>
let currentSessionId = null;
let step = "line";
let sessionPlayers = [];

function selectedPlayers() {
  const selected = [...document.querySelectorAll('input[name="winner"]:checked')].map(el => el.value);
  return selected;
}

function renderWinners(players) {
  const box = document.getElementById("winners");
  box.innerHTML = players.map(p => `<label><input type="checkbox" name="winner" value="${p}"> ${p}</label>`).join(" ");
}

async function refreshHistory() {
  if (!currentSessionId) return;
  const res = await fetch(`/sessions/${currentSessionId}`);
  const data = await res.json();
  document.getElementById("history").textContent = JSON.stringify(data, null, 2);
}

document.getElementById("createSessionForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const players = document.getElementById("players").value.split(",").map(p => p.trim()).filter(Boolean);
  const cardPrice = Number(document.getElementById("cardPrice").value);
  const lineBonus = Number(document.getElementById("lineBonus").value);

  const res = await fetch("/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ players, card_price_kopecks: cardPrice, line_bonus_kopecks: lineBonus })
  });
  const data = await res.json();
  currentSessionId = data.session_id;
  sessionPlayers = data.players;
  step = "line";

  document.getElementById("sessionInfo").textContent = `Сессия #${currentSessionId} создана`;
  document.getElementById("gameFlow").classList.remove("hidden");
  document.getElementById("question").textContent = "Кто закрыл линию?";
  renderWinners(sessionPlayers);
  await refreshHistory();
});

document.getElementById("confirmStep").addEventListener("click", async () => {
  if (!currentSessionId) return;
  const players = selectedPlayers();
  if (!players.length) {
    alert("Выберите хотя бы одного игрока");
    return;
  }

  if (step === "line") {
    await fetch(`/sessions/${currentSessionId}/line`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ players })
    });
    step = "card";
    document.getElementById("question").textContent = "Кто закрыл карту?";
    renderWinners(sessionPlayers);
  } else {
    await fetch(`/sessions/${currentSessionId}/card`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ players })
    });
    await fetch(`/sessions/${currentSessionId}/finish`, { method: "POST" });
    step = "line";
    document.getElementById("question").textContent = "Игра завершена. Начните новую игру в сессии";
  }

  await refreshHistory();
});

document.getElementById("newGame").addEventListener("click", async () => {
  if (!currentSessionId) return;
  await fetch(`/sessions/${currentSessionId}/new-game`, { method: "POST" });
  step = "line";
  document.getElementById("question").textContent = "Кто закрыл линию?";
  renderWinners(sessionPlayers);
  await refreshHistory();
});
</script>
</body>
</html>
"""


@app.post("/sessions")
def create_session(payload: SessionCreateRequest) -> dict[str, Any]:
    players = [player.strip() for player in payload.players if player.strip()]
    if len(set(players)) < 2:
        raise HTTPException(status_code=400, detail="at least two unique players required")

    session_id = next(session_counter)
    SESSIONS[session_id] = {
        "session_id": session_id,
        "players": players,
        "card_price_kopecks": payload.card_price_kopecks,
        "line_bonus_kopecks": payload.line_bonus_kopecks,
        "created_at": datetime.utcnow().isoformat(),
        "active_game": {
            "game_number": 1,
            "line_winners": [],
            "card_winners": [],
        },
        "history": [],
    }
    return SESSIONS[session_id]


@app.post("/sessions/{session_id}/line")
def session_line(session_id: int, payload: SessionWinnersRequest) -> dict[str, Any]:
    session = _session_or_404(session_id)
    winners = _validate_winners(session, payload.players)
    session["active_game"]["line_winners"] = winners
    return {"status": "ok", "line_winners": winners}


@app.post("/sessions/{session_id}/card")
def session_card(session_id: int, payload: SessionWinnersRequest) -> dict[str, Any]:
    session = _session_or_404(session_id)
    winners = _validate_winners(session, payload.players)
    session["active_game"]["card_winners"] = winners
    return {"status": "ok", "card_winners": winners}


@app.post("/sessions/{session_id}/finish")
def finish_session_game(session_id: int) -> dict[str, Any]:
    session = _session_or_404(session_id)
    game = session["active_game"]
    if not game["card_winners"]:
        raise HTTPException(status_code=400, detail="card winners are required before finish")

    settings = GameSettings(
        card_price_kopecks=session["card_price_kopecks"],
        line_bonus_kopecks=session["line_bonus_kopecks"],
    )
    net = calculate_net(
        players=session["players"],
        settings=settings,
        line_winners=game["line_winners"],
        card_winners=game["card_winners"],
    )
    result = {
        "game_number": game["game_number"],
        "line_winners": game["line_winners"],
        "card_winners": game["card_winners"],
        "net": net,
        "transfers": build_transfers(net),
        "finished_at": datetime.utcnow().isoformat(),
    }
    session["history"].append(result)
    return result


@app.post("/sessions/{session_id}/new-game")
def new_game_in_session(session_id: int) -> dict[str, Any]:
    session = _session_or_404(session_id)
    next_number = len(session["history"]) + 1
    session["active_game"] = {
        "game_number": next_number,
        "line_winners": [],
        "card_winners": [],
    }
    return session["active_game"]


@app.get("/sessions/{session_id}")
def get_session(session_id: int) -> dict[str, Any]:
    return _session_or_404(session_id)


def _session_or_404(session_id: int) -> dict[str, Any]:
    session = SESSIONS.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return session


def _validate_winners(session: dict[str, Any], winners: list[str]) -> list[str]:
    normalized = []
    seen = set()
    for winner in winners:
        name = winner.strip()
        if not name:
            continue
        if name not in session["players"]:
            raise HTTPException(status_code=400, detail=f"unknown player: {name}")
        if name not in seen:
            seen.add(name)
            normalized.append(name)

    if not normalized:
        raise HTTPException(status_code=400, detail="at least one winner is required")
    return normalized
