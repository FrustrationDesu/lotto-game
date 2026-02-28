from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from typing import FrozenSet, Tuple


class DomainValidationError(ValueError):
    """Ошибка валидации доменной логики."""


@dataclass(frozen=True)
class GameSettings:
    card_price_kopecks: int
    line_bonus_kopecks: int

    def __post_init__(self) -> None:
        if self.card_price_kopecks <= 0:
            raise DomainValidationError("Стоимость карточки должна быть положительной.")
        if self.line_bonus_kopecks < 0:
            raise DomainValidationError("Бонус за линию не может быть отрицательным.")


class GameEventType(str, Enum):
    LINE_CLOSED = "LINE_CLOSED"
    CARD_CLOSED = "CARD_CLOSED"


@dataclass(frozen=True)
class GameEvent:
    event_type: GameEventType
    player_ids: Tuple[str, ...]
    occurred_at: datetime | None = None
    sequence: int | None = None

    def __post_init__(self) -> None:
        if not self.player_ids:
            raise DomainValidationError("Событие должно содержать хотя бы одного игрока.")
        normalized_ids = tuple(player_id.strip() for player_id in self.player_ids)
        if any(not player_id for player_id in normalized_ids):
            raise DomainValidationError("Идентификатор игрока не может быть пустым.")
        if len(set(normalized_ids)) != len(normalized_ids):
            raise DomainValidationError("В одном событии игрок не может дублироваться.")
        object.__setattr__(self, "player_ids", normalized_ids)


@dataclass(frozen=True)
class GameState:
    players: FrozenSet[str]
    events: Tuple[GameEvent, ...] = field(default_factory=tuple)
    finished_at: datetime | None = None
    winners: FrozenSet[str] = field(default_factory=frozenset)
    line_winners: FrozenSet[str] = field(default_factory=frozenset)



def apply_event(state: GameState, event: GameEvent) -> GameState:
    """Применяет доменное событие к состоянию партии без инфраструктурных зависимостей."""
    _ensure_players_exist(state, event)

    if event.event_type is GameEventType.LINE_CLOSED:
        repeated_line_closers = set(event.player_ids).intersection(state.line_winners)
        if repeated_line_closers:
            repeated = ", ".join(sorted(repeated_line_closers))
            raise DomainValidationError(
                f"Игрок(и) уже закрывали линию в этой партии: {repeated}."
            )

        return replace(
            state,
            events=state.events + (event,),
            line_winners=state.line_winners.union(event.player_ids),
        )

    if event.event_type is GameEventType.CARD_CLOSED:
        finished_at = state.finished_at or event.occurred_at or datetime.utcnow()
        return replace(
            state,
            events=state.events + (event,),
            winners=state.winners.union(event.player_ids),
            finished_at=finished_at,
        )

    raise DomainValidationError(f"Неподдерживаемый тип события: {event.event_type}")



def _ensure_players_exist(state: GameState, event: GameEvent) -> None:
    unknown_players = [player_id for player_id in event.player_ids if player_id not in state.players]
    if unknown_players:
        missing_players = ", ".join(sorted(unknown_players))
        raise DomainValidationError(
            f"В событии есть игроки, не участвующие в партии: {missing_players}."
        )
