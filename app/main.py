from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.domain import DomainValidationError, GameEvent, GameEventType
from app.repository import LottoRepository
from app.service import LottoService


class StartGameRequest(BaseModel):
    players: list[str] = Field(min_length=2)
    card_price_kopecks: int = Field(gt=0)
    line_bonus_kopecks: int = Field(gt=0)


class EventRequest(BaseModel):
    players: list[str] = Field(min_length=1)


repo = LottoRepository()
service = LottoService(repo)
app = FastAPI(title="Lotto Game API")


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
        service.add_event(game_id, GameEvent(type=GameEventType.LINE_CLOSED, players=tuple(payload.players)))
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok"}


@app.post("/games/{game_id}/events/card")
def add_card_event(game_id: int, payload: EventRequest) -> dict[str, str]:
    try:
        service.add_event(game_id, GameEvent(type=GameEventType.CARD_CLOSED, players=tuple(payload.players)))
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
