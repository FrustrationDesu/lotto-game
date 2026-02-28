from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from app.api.errors import api_error
from app.api.speech_schemas import SpeechInterpretRequest, SpeechInterpretResponse
from app.runtime import command_parser
from app.services.command_parser import EventType, ParseStatus
from app.services.transcription_service import (
    TranscriptionConfigError,
    TranscriptionProviderError,
    transcribe_audio,
)

router = APIRouter(prefix="/speech", tags=["speech"])

_ALLOWED_AUDIO_MIME_TYPES = {"audio/webm", "audio/wav", "audio/mpeg", "audio/mp4"}


@router.post("/interpret", response_model=SpeechInterpretResponse)
def interpret(payload: SpeechInterpretRequest) -> SpeechInterpretResponse:
    parsed = command_parser.parse(text=payload.text, players=payload.players)

    intent = "unknown"
    endpoint = None
    if parsed.event_type == EventType.CLOSE_LINE:
        intent = "close_line"
        endpoint = "/games/{game_id}/events/line"
    elif parsed.event_type == EventType.CLOSE_CARD:
        intent = "close_card"
        endpoint = "/games/{game_id}/events/card"

    errors = [parsed.error] if parsed.error else []
    if parsed.status != ParseStatus.OK:
        endpoint = None

    return SpeechInterpretResponse(
        raw_text=parsed.raw_text or payload.text,
        normalized_text=parsed.normalized_text or payload.text,
        intent=intent,
        confidence=parsed.confidence,
        player_id=parsed.player_name,
        event_endpoint=endpoint,
        errors=errors,
    )


@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...)) -> dict[str, str | float | None]:
    if file.content_type not in _ALLOWED_AUDIO_MIME_TYPES:
        raise api_error(
            code="unsupported_audio_type",
            message=f"Unsupported MIME type: {file.content_type}",
        )

    data = await file.read()
    if not data:
        raise api_error(code="empty_audio_payload", message="Empty audio payload")

    try:
        result = transcribe_audio(
            filename=file.filename or "recording.webm",
            content_type=file.content_type or "application/octet-stream",
            data=data,
        )
    except TranscriptionConfigError as exc:
        # fallback for local demo without provider config
        return {
            "text": "тестовая транскрипция",
            "language": "ru",
            "duration_seconds": None,
            "provider": "mock-media-recorder",
        }
    except TranscriptionProviderError as exc:
        raise api_error(
            code="transcription_provider_error",
            message=str(exc),
            status_code=exc.status_code,
        ) from exc

    return {
        "text": result.text,
        "language": result.language,
        "duration_seconds": result.duration_seconds,
        "provider": result.provider,
    }
