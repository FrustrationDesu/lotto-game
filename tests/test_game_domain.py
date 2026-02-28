from datetime import datetime

import pytest

from app.domain.game import (
    DomainValidationError,
    GameEvent,
    GameEventType,
    GameSettings,
    GameState,
    apply_event,
)


def test_settings_validation() -> None:
    with pytest.raises(DomainValidationError):
        GameSettings(card_price_kopecks=0, line_bonus_kopecks=1)

    with pytest.raises(DomainValidationError):
        GameSettings(card_price_kopecks=100, line_bonus_kopecks=-1)


def test_apply_line_closed_once_per_player() -> None:
    state = GameState(players=frozenset({"p1", "p2"}))
    event = GameEvent(event_type=GameEventType.LINE_CLOSED, player_ids=("p1", "p2"))

    new_state = apply_event(state, event)

    assert new_state.line_winners == frozenset({"p1", "p2"})

    with pytest.raises(DomainValidationError):
        apply_event(
            new_state,
            GameEvent(event_type=GameEventType.LINE_CLOSED, player_ids=("p2",)),
        )


def test_apply_card_closed_supports_multiple_winners_and_keeps_first_finish_time() -> None:
    state = GameState(players=frozenset({"p1", "p2", "p3"}))
    first = GameEvent(
        event_type=GameEventType.CARD_CLOSED,
        player_ids=("p1", "p2"),
        occurred_at=datetime(2025, 1, 1, 10, 0, 0),
        sequence=10,
    )
    second = GameEvent(
        event_type=GameEventType.CARD_CLOSED,
        player_ids=("p3",),
        occurred_at=datetime(2025, 1, 1, 10, 0, 0),
        sequence=10,
    )

    first_state = apply_event(state, first)
    second_state = apply_event(first_state, second)

    assert second_state.winners == frozenset({"p1", "p2", "p3"})
    assert second_state.finished_at == datetime(2025, 1, 1, 10, 0, 0)


def test_unknown_players_rejected() -> None:
    state = GameState(players=frozenset({"known"}))

    with pytest.raises(DomainValidationError):
        apply_event(
            state,
            GameEvent(event_type=GameEventType.CARD_CLOSED, player_ids=("unknown",)),
        )
