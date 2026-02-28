from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.api.speech_schemas import SpeechInterpretRequest, SpeechInterpretResponse
from app.services.command_parser import CommandParser, EventType, ParseStatus
from app.services.transcription_service import (
    TranscriptionConfigError,
    TranscriptionProviderError,
    transcribe_audio as default_transcribe_audio,
)

router = APIRouter(prefix="/speech", tags=["speech"])

parser = CommandParser()

SUPPORTED_MIME_TYPES = {
    "audio/webm",
    "audio/wav",
    "audio/mpeg",
    "audio/mp4",
    "audio/x-m4a",
}




def _resolve_transcribe_audio():
    try:
        from app import main as main_module

        return getattr(main_module, "transcribe_audio", default_transcribe_audio)
    except Exception:
        return default_transcribe_audio


@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...)) -> dict[str, str | float | None]:
    if file.content_type not in SUPPORTED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported MIME type: {file.content_type}",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty audio payload")

    try:
        result = _resolve_transcribe_audio()(
            filename=file.filename or "audio",
            content_type=file.content_type,
            data=data,
        )
    except TranscriptionProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except TranscriptionConfigError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return {
        "text": result.text,
        "language": result.language,
        "duration_seconds": result.duration_seconds,
        "provider": result.provider,
    }


@router.post("/interpret", response_model=SpeechInterpretResponse)
def interpret(payload: SpeechInterpretRequest) -> SpeechInterpretResponse:
    parsed = parser.parse(payload.text, payload.players)

    intent: Literal["close_line", "close_card", "unknown"] = "unknown"
    endpoint = None
    player_id = None
    confidence = None
    errors: list[str] = []

    if parsed.status is ParseStatus.OK and parsed.event_type is not None:
        confidence = parsed.confidence
        player_id = parsed.player_name
        if parsed.event_type is EventType.CLOSE_LINE:
            intent = "close_line"
            endpoint = "/games/{game_id}/events/line"
        elif parsed.event_type is EventType.CLOSE_CARD:
            intent = "close_card"
            endpoint = "/games/{game_id}/events/card"
    else:
        errors.append(parsed.error or "Не удалось интерпретировать команду")

    return SpeechInterpretResponse(
        raw_text=parsed.raw_text or payload.text,
        normalized_text=parsed.normalized_text or payload.text,
        intent=intent,
        confidence=confidence,
        player_id=player_id,
        event_endpoint=endpoint,
        errors=errors,
    )
