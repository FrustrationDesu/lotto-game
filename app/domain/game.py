from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from typing import FrozenSet, Iterable, Tuple


class DomainValidationError(ValueError):
    """Raised when a game rule is violated."""


@dataclass(frozen=True)
class GameSettings:
    card_price_kopecks: int
    line_bonus_kopecks: int

    def __post_init__(self) -> None:
        if self.card_price_kopecks <= 0:
            raise DomainValidationError("card_price_kopecks must be positive")
        if self.line_bonus_kopecks <= 0:
            raise DomainValidationError("line_bonus_kopecks must be positive")


class GameEventType(str, Enum):
    LINE_CLOSED = "line_closed"
    CARD_CLOSED = "card_closed"


@dataclass(frozen=True)
class GameEvent:
    event_type: GameEventType
    player_ids: Tuple[str, ...]
    occurred_at: datetime | None = None
    sequence: int | None = None

    def __post_init__(self) -> None:
        normalized_ids = tuple(normalize_player(player_id) for player_id in self.player_ids)
        if not normalized_ids:
            raise DomainValidationError("event must have at least one player")
        if len(set(normalized_ids)) != len(normalized_ids):
            raise DomainValidationError("players in event must be unique")
        object.__setattr__(self, "player_ids", normalized_ids)


@dataclass(frozen=True)
class GameState:
    players: FrozenSet[str]
    events: Tuple[GameEvent, ...] = field(default_factory=tuple)
    finished_at: datetime | None = None
    winners: FrozenSet[str] = field(default_factory=frozenset)
    line_winners: FrozenSet[str] = field(default_factory=frozenset)


def normalize_player(name: str) -> str:
    value = name.strip()
    if not value:
        raise DomainValidationError("player name must be non-empty")
    return value


def unique_preserve_order(players: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for player in players:
        normalized = normalize_player(player)
        if normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def apply_event(state: GameState, event: GameEvent) -> GameState:
    """Apply a domain event to a game state without infrastructure dependencies."""
    _ensure_players_exist(state, event)

    if event.event_type == GameEventType.LINE_CLOSED:
        repeated_line_closers = set(event.player_ids).intersection(state.line_winners)
        if repeated_line_closers:
            repeated = ", ".join(sorted(repeated_line_closers))
            raise DomainValidationError(f"line already closed by: {repeated}")

        return replace(
            state,
            events=state.events + (event,),
            line_winners=state.line_winners.union(event.player_ids),
        )

    if event.event_type == GameEventType.CARD_CLOSED:
        finished_at = state.finished_at or event.occurred_at or datetime.utcnow()
        return replace(
            state,
            events=state.events + (event,),
            winners=state.winners.union(event.player_ids),
            finished_at=finished_at,
        )

    raise DomainValidationError(f"unsupported event type: {event.event_type}")


def _ensure_players_exist(state: GameState, event: GameEvent) -> None:
    unknown_players = [player_id for player_id in event.player_ids if player_id not in state.players]
    if unknown_players:
        missing_players = ", ".join(sorted(unknown_players))
        raise DomainValidationError(f"unknown players in event: {missing_players}")
