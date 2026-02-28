from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SpeechInterpretRequest(BaseModel):
    text: str = Field(..., description="Текст, распознанный ASR/Whisper")
    players: list[str] = Field(
        default_factory=list,
        description="Список игроков, среди которых нужно определить победителя",
    )


class SpeechInterpretResponse(BaseModel):
    raw_text: str
    normalized_text: str
    intent: Literal["close_line", "close_card", "unknown"]
    confidence: float | None = None
    player_id: str | None = None
    event_endpoint: str | None = None
    errors: list[str] = Field(default_factory=list)

