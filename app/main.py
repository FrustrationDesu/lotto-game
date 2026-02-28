from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi import File, UploadFile
from pydantic import BaseModel, Field

from app.api.speech_schemas import SpeechInterpretRequest, SpeechInterpretResponse
from app.domain import DomainValidationError, GameEvent, GameEventType
from app.repository import LottoRepository
from app.services.command_parser import CommandParser, EventType, ParseStatus
from app.service import LottoService


class StartGameRequest(BaseModel):
    players: list[str] = Field(min_length=2)
    card_price_kopecks: int = Field(gt=0)
    line_bonus_kopecks: int = Field(gt=0)


class EventRequest(BaseModel):
    players: list[str] = Field(min_length=1)


repo = LottoRepository()
service = LottoService(repo)
command_parser = CommandParser()
app = FastAPI(title="Lotto Game API")

ALLOWED_AUDIO_TYPES = {"audio/webm", "audio/wav", "audio/mpeg"}
MAX_AUDIO_FILE_SIZE_BYTES = int(os.getenv("MAX_AUDIO_FILE_SIZE_BYTES", str(10 * 1024 * 1024)))


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


@app.post("/speech/interpret", response_model=SpeechInterpretResponse)
def interpret_speech_command(payload: SpeechInterpretRequest) -> SpeechInterpretResponse:
    result = command_parser.parse_whisper_output(payload.text, payload.players)

    intent_map = {
        EventType.CLOSE_LINE: "close_line",
        EventType.CLOSE_CARD: "close_card",
    }
    endpoint_map = {
        EventType.CLOSE_LINE: "/games/{game_id}/events/line",
        EventType.CLOSE_CARD: "/games/{game_id}/events/card",
    }

    errors: list[str] = []
    if result.status is not ParseStatus.OK:
        if result.error:
            errors.append(result.error)
        if result.candidates:
            options = ", ".join(candidate["player_name"] for candidate in result.candidates)
            errors.append(f"Возможные игроки: {options}")

    return SpeechInterpretResponse(
        raw_text=result.raw_text or payload.text,
        normalized_text=result.normalized_text or "",
        intent=intent_map.get(result.event_type, "unknown"),
        confidence=result.confidence,
        player_id=result.player_name,
        event_endpoint=endpoint_map.get(result.event_type),
        errors=errors,
    )
