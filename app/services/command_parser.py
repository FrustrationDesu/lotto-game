from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import Enum
from typing import Iterable


class ParseStatus(str, Enum):
    OK = "OK"
    UNKNOWN_COMMAND = "UNKNOWN_COMMAND"
    EMPTY_NAME = "EMPTY_NAME"
    PLAYER_NOT_FOUND = "PLAYER_NOT_FOUND"
    AMBIGUOUS_NAME = "AMBIGUOUS_NAME"


class EventType(str, Enum):
    CLOSE_LINE = "CLOSE_LINE"
    CLOSE_CARD = "CLOSE_CARD"


@dataclass(slots=True)
class ParseResult:
    status: ParseStatus
    event_type: EventType | None = None
    player_name: str | None = None
    confidence: float | None = None
    raw_text: str | None = None
    normalized_text: str | None = None
    candidates: list[dict[str, float | str]] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict:
        """Structured payload suitable for subsequent event API calls."""
        return {
            "status": self.status.value,
            "event_type": self.event_type.value if self.event_type else None,
            "player_name": self.player_name,
            "confidence": self.confidence,
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "candidates": self.candidates,
            "error": self.error,
        }


@dataclass(slots=True)
class ParserConfig:
    confidence_threshold: int = 80
    ambiguity_delta: int = 5
    max_ambiguous_candidates: int = 3


class CommandParser:
    _COMMAND_PATTERNS: tuple[tuple[EventType, re.Pattern[str]], ...] = (
        (EventType.CLOSE_LINE, re.compile(r"^закрыл линию\s+(.+)$")),
        (EventType.CLOSE_CARD, re.compile(r"^закрыл карту\s+(.+)$")),
    )

    def __init__(self, config: ParserConfig | None = None) -> None:
        self.config = config or ParserConfig()

    def parse(self, text: str, players: Iterable[str]) -> ParseResult:
        normalized_text = normalize_text(text)
        matched_command = self._extract_command(normalized_text)

        if matched_command is None:
            return ParseResult(
                status=ParseStatus.UNKNOWN_COMMAND,
                raw_text=text,
                normalized_text=normalized_text,
                error="Команда не распознана",
            )

        event_type, requested_name = matched_command
        if not requested_name:
            return ParseResult(
                status=ParseStatus.EMPTY_NAME,
                event_type=event_type,
                raw_text=text,
                normalized_text=normalized_text,
                error="Имя игрока не указано",
            )

        match = self._match_player(requested_name=requested_name, players=players)
        if match["status"] is not ParseStatus.OK:
            return ParseResult(
                status=match["status"],
                event_type=event_type,
                raw_text=text,
                normalized_text=normalized_text,
                candidates=match.get("candidates", []),
                error=match.get("error"),
            )

        return ParseResult(
            status=ParseStatus.OK,
            event_type=event_type,
            player_name=match["player_name"],
            confidence=match["confidence"],
            raw_text=text,
            normalized_text=normalized_text,
        )

    def parse_whisper_output(self, payload: str | dict, players: Iterable[str]) -> ParseResult:
        """Parse plain text or Whisper-like payloads containing transcript text."""
        if isinstance(payload, str):
            raw_text = payload
        elif isinstance(payload, dict):
            raw_text = str(payload.get("text") or payload.get("transcript") or "")
        else:
            raw_text = ""
        return self.parse(text=raw_text, players=players)

    def _extract_command(self, normalized_text: str) -> tuple[EventType, str] | None:
        for event_type, pattern in self._COMMAND_PATTERNS:
            matched = pattern.match(normalized_text)
            if matched:
                requested_name = matched.group(1).strip()
                return event_type, requested_name
        return None

    def _match_player(self, requested_name: str, players: Iterable[str]) -> dict:
        players_list = [player for player in players if player and player.strip()]
        if not players_list:
            return {
                "status": ParseStatus.PLAYER_NOT_FOUND,
                "error": "Список игроков пуст",
            }

        normalized_to_original: dict[str, str] = {}
        for player in players_list:
            normalized_to_original[normalize_text(player)] = player

        normalized_players = list(normalized_to_original.keys())
        matches = self._extract_matches(requested_name, normalized_players)

        if not matches:
            return {
                "status": ParseStatus.PLAYER_NOT_FOUND,
                "error": "Игрок не найден",
            }

        best_name, best_score = matches[0]

        if best_score < self.config.confidence_threshold:
            return {
                "status": ParseStatus.PLAYER_NOT_FOUND,
                "candidates": self._build_candidates(matches, normalized_to_original),
                "error": "Недостаточная уверенность в совпадении",
            }

        ambiguous_candidates = [
            (name, score)
            for name, score in matches
            if score >= self.config.confidence_threshold
            and (best_score - score) <= self.config.ambiguity_delta
        ]

        if len(ambiguous_candidates) > 1:
            return {
                "status": ParseStatus.AMBIGUOUS_NAME,
                "candidates": [
                    {
                        "player_name": normalized_to_original[name],
                        "confidence": float(score),
                    }
                    for name, score in ambiguous_candidates
                ],
                "error": "Найдено несколько похожих игроков",
            }

        return {
            "status": ParseStatus.OK,
            "player_name": normalized_to_original[best_name],
            "confidence": float(best_score),
        }

    def _extract_matches(self, requested_name: str, normalized_players: list[str]) -> list[tuple[str, int]]:
        scored = [
            (name, int(SequenceMatcher(None, requested_name, name).ratio() * 100))
            for name in normalized_players
        ]
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[: self.config.max_ambiguous_candidates]

    def _build_candidates(
        self,
        matches: list[tuple[str, int]],
        normalized_to_original: dict[str, str],
    ) -> list[dict[str, float | str]]:
        return [
            {"player_name": normalized_to_original[name], "confidence": float(score)}
            for name, score in matches
        ]


def normalize_text(value: str) -> str:
    value = value.lower().replace("ё", "е")
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    value = re.sub(r"\s+", " ", value).strip()
    return value
