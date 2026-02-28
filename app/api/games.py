from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.errors import api_error
from app.domain import DomainValidationError, GameEvent, GameEventType
from app.runtime import service

router = APIRouter(prefix="/games", tags=["games"])


class StartGameRequest(BaseModel):
    players: list[str] = Field(min_length=2)
    card_price_kopecks: int = Field(gt=0)
    line_bonus_kopecks: int = Field(gt=0)


class EventRequest(BaseModel):
    players: list[str] = Field(min_length=1)


@router.post("")
def start_game(payload: StartGameRequest) -> dict[str, int]:
    try:
        game_id = service.start_game(
            payload.players,
            payload.card_price_kopecks,
            payload.line_bonus_kopecks,
        )
    except DomainValidationError as exc:
        raise api_error(code="invalid_game", message=str(exc)) from exc
    return {"game_id": game_id}


@router.post("/{game_id}/events/line")
def add_line_event(game_id: int, payload: EventRequest) -> dict[str, str]:
    try:
        service.add_event(
            game_id,
            GameEvent(type=GameEventType.LINE_CLOSED, players=tuple(payload.players)),
        )
    except DomainValidationError as exc:
        raise api_error(code="invalid_event", message=str(exc)) from exc
    return {"status": "ok"}


@router.post("/{game_id}/events/card")
def add_card_event(game_id: int, payload: EventRequest) -> dict[str, str]:
    try:
        service.add_event(
            game_id,
            GameEvent(type=GameEventType.CARD_CLOSED, players=tuple(payload.players)),
        )
    except DomainValidationError as exc:
        raise api_error(code="invalid_event", message=str(exc)) from exc
    return {"status": "ok"}


@router.post("/{game_id}/finish")
def finish_game(game_id: int) -> dict[str, object]:
    try:
        return service.finish_game(game_id)
    except DomainValidationError as exc:
        raise api_error(code="invalid_game_state", message=str(exc)) from exc


@router.get("/{game_id}/settlement")
def settlement(game_id: int) -> dict[str, object]:
    try:
        return service.get_settlement(game_id)
    except DomainValidationError as exc:
        raise api_error(code="invalid_game_state", message=str(exc)) from exc
