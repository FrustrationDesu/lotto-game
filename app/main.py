from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
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


class SpeechTranscribeResponse(BaseModel):
    text: str
    language: str
    provider: str


repo = LottoRepository()
service = LottoService(repo)
command_parser = CommandParser()
app = FastAPI(title="Lotto Game API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.post("/speech/transcribe", response_model=SpeechTranscribeResponse)
async def speech_transcribe(file: UploadFile = File(...)) -> SpeechTranscribeResponse:
    if file.content_type not in {"audio/webm", "audio/webm;codecs=opus", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="Unsupported audio format")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty audio payload")

    return SpeechTranscribeResponse(
        text="Тестовая расшифровка получена",
        language="ru",
        provider="mock-media-recorder",
    )
