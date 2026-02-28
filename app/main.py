from __future__ import annotations

from datetime import datetime
from itertools import count
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.speech import router as speech_router
from app.domain import DomainValidationError, GameEvent, GameEventType, GameSettings, build_transfers, calculate_net
from app.repository import LottoRepository
from app.service import LottoService
from app.services.command_parser import CommandParser, EventType, ParseStatus


class StartGameRequest(BaseModel):
    players: list[str] = Field(min_length=2)
    card_price_kopecks: int = Field(gt=0)
    line_bonus_kopecks: int = Field(gt=0)


class EventRequest(BaseModel):
    players: list[str] = Field(min_length=1)


class SessionCreateRequest(BaseModel):
    players: list[str] = Field(min_length=2)
    card_price_kopecks: int = Field(gt=0)
    line_bonus_kopecks: int = Field(gt=0)


class SessionWinnersRequest(BaseModel):
    players: list[str] = Field(min_length=1)


class SpeechInterpretRequest(BaseModel):
    text: str
    players: list[str] = Field(default_factory=list)


repo = LottoRepository()
service = LottoService(repo)
command_parser = CommandParser()
app = FastAPI(title="Lotto Game API")
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
    .history-layout { display: grid; gap: 1rem; }
    table { width: 100%; border-collapse: collapse; }
    th, td { border: 1px solid #ddd; padding: 0.45rem 0.6rem; vertical-align: top; }
    th { background: #f7f7f7; text-align: left; }
    .num { text-align: right; font-variant-numeric: tabular-nums; }
    .money-positive { color: #0b7a0b; font-weight: 600; }
    .money-negative { color: #b42318; font-weight: 600; }
    .money-zero { color: #667085; }
    .friendly-state { margin: 0; color: #667085; font-style: italic; }
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
    <div id="history" class="history-layout">
      <p class="friendly-state">Сессия еще не создана</p>
    </div>
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

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatRub(valueKopecks) {
  const amountRub = Number(valueKopecks || 0) / 100;
  return `${amountRub.toFixed(2)} ₽`;
}

function moneyClass(valueKopecks) {
  if (valueKopecks > 0) return "money-positive";
  if (valueKopecks < 0) return "money-negative";
  return "money-zero";
}

function formatFinishedAt(isoValue) {
  if (!isoValue) return "—";
  const parsed = new Date(isoValue);
  if (Number.isNaN(parsed.getTime())) return escapeHtml(isoValue);
  return parsed.toLocaleString("ru-RU");
}

async function refreshHistory() {
  if (!currentSessionId) return;
  const res = await fetch(`/sessions/${currentSessionId}`);
  const data = await res.json();
  const historyRoot = document.getElementById("history");
  const games = Array.isArray(data.history) ? data.history : [];
  const playerBalances = Object.fromEntries((data.players || []).map((player) => [player, 0]));

  for (const game of games) {
    const net = game.net || {};
    for (const [player, value] of Object.entries(net)) {
      playerBalances[player] = (playerBalances[player] || 0) + Number(value || 0);
    }
  }

  if (!games.length) {
    historyRoot.innerHTML = '<p class="friendly-state">Пока нет завершенных игр</p>';
    return;
  }

  const gameRows = games.map((game) => {
    const netEntries = Object.entries(game.net || {})
      .map(([player, value]) => `<div><strong>${escapeHtml(player)}</strong>: <span class="${moneyClass(value)}">${formatRub(value)}</span></div>`)
      .join("");
    return `
      <tr>
        <td class="num">${escapeHtml(game.game_number)}</td>
        <td>${escapeHtml((game.line_winners || []).join(", ") || "—")}</td>
        <td>${escapeHtml((game.card_winners || []).join(", ") || "—")}</td>
        <td>${netEntries || "—"}</td>
        <td>${escapeHtml(formatFinishedAt(game.finished_at))}</td>
      </tr>
    `;
  }).join("");

  const balanceRows = Object.entries(playerBalances).map(([player, value]) => `
      <tr>
        <td>${escapeHtml(player)}</td>
        <td class="num ${moneyClass(value)}">${formatRub(value)}</td>
        <td class="num">${Number(value || 0)}</td>
      </tr>
    `).join("");

  historyRoot.innerHTML = `
    <section>
      <h3>История игр</h3>
      <table>
        <thead>
          <tr>
            <th>№ игры</th>
            <th>Победители линии</th>
            <th>Победители карты</th>
            <th>Net (₽)</th>
            <th>Завершена</th>
          </tr>
        </thead>
        <tbody>${gameRows}</tbody>
      </table>
    </section>
    <section>
      <h3>Текущий баланс</h3>
      <table>
        <thead>
          <tr>
            <th>Игрок</th>
            <th>Баланс (₽)</th>
            <th>Баланс (коп)</th>
          </tr>
        </thead>
        <tbody>${balanceRows}</tbody>
      </table>
    </section>
  `;
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


@app.post("/games")
def start_game(payload: StartGameRequest) -> dict[str, int]:
    try:
        game_id = service.start_game(
            payload.players, payload.card_price_kopecks, payload.line_bonus_kopecks
        )
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"game_id": game_id}


@app.post("/games/{game_id}/events/line")
def add_line_event(game_id: int, payload: EventRequest) -> dict[str, str]:
    try:
        service.add_event(game_id, GameEvent(event_type=GameEventType.LINE_CLOSED, player_ids=tuple(payload.players)))
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok"}


@app.post("/games/{game_id}/events/card")
def add_card_event(game_id: int, payload: EventRequest) -> dict[str, str]:
    try:
        service.add_event(game_id, GameEvent(event_type=GameEventType.CARD_CLOSED, player_ids=tuple(payload.players)))
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok"}


@app.post("/games/{game_id}/finish")
def finish_game(game_id: int) -> dict[str, object]:
    try:
        return service.finish_game(game_id)
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/games/{game_id}/settlement")
def settlement(game_id: int) -> dict[str, object]:
    try:
        return service.get_settlement(game_id)
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/stats/balance")
def stats() -> dict[str, object]:
    return service.get_stats()


@app.post("/speech/interpret")
def speech_interpret(payload: SpeechInterpretRequest) -> dict[str, object]:
    parsed = command_parser.parse(payload.text, payload.players)

    endpoint_map = {
        EventType.CLOSE_LINE: "/games/{game_id}/events/line",
        EventType.CLOSE_CARD: "/games/{game_id}/events/card",
    }

    if parsed.status is ParseStatus.OK:
        return {
            "raw_text": parsed.raw_text,
            "normalized_text": parsed.normalized_text,
            "intent": "close_line" if parsed.event_type is EventType.CLOSE_LINE else "close_card",
            "confidence": parsed.confidence,
            "player_id": parsed.player_name,
            "event_endpoint": endpoint_map.get(parsed.event_type),
            "errors": [],
        }

    return {
        "raw_text": parsed.raw_text,
        "normalized_text": parsed.normalized_text,
        "intent": "unknown",
        "confidence": None,
        "player_id": None,
        "event_endpoint": None,
        "errors": [parsed.error] if parsed.error else [parsed.status.value],
    }


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
