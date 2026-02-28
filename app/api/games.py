from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException, status

from app.api.schemas import (
    CreateGameRequest,
    CreateGameResponse,
    GameStateResponse,
    SettlementResponse,
    WinnerEventRequest,
)

router = APIRouter(prefix="/games", tags=["games"])

GAMES: dict[str, dict] = {}


def _get_game_or_404(game_id: str) -> dict:
    game = GAMES.get(game_id)
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "game_not_found",
                "message": f"Игра {game_id} не найдена",
                "details": {"id": game_id},
            },
        )
    return game


def _ensure_player(game: dict, player_id: str) -> None:
    if player_id not in game["players"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_player",
                "message": "Игрок не участвует в партии",
                "details": {"player_id": player_id},
            },
        )


@router.post(
    "",
    response_model=CreateGameResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать новую партию",
)
def create_game(payload: CreateGameRequest) -> CreateGameResponse:
    game_id = str(uuid4())
    game = {
        "id": game_id,
        "players": payload.players,
        "card_price": payload.card_price,
        "line_bonus": payload.line_bonus,
        "line_winner": None,
        "card_winner": None,
        "status": "active",
    }
    GAMES[game_id] = game
    return CreateGameResponse(**game)


@router.post(
    "/{id}/events/line",
    response_model=GameStateResponse,
    summary="Зафиксировать победителя по линии",
)
def mark_line_event(id: str, payload: WinnerEventRequest) -> GameStateResponse:
    game = _get_game_or_404(id)
    if game["status"] == "finished":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "game_already_finished",
                "message": "Партия уже завершена",
                "details": {"id": id},
            },
        )
    if game["line_winner"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "line_winner_already_set",
                "message": "Победитель по линии уже зафиксирован",
                "details": {"winner": game['line_winner']},
            },
        )
    _ensure_player(game, payload.player_id)
    game["line_winner"] = payload.player_id
    return GameStateResponse(
        id=id,
        status=game["status"],
        line_winner=game["line_winner"],
        card_winner=game["card_winner"],
    )


@router.post(
    "/{id}/events/card",
    response_model=GameStateResponse,
    summary="Зафиксировать победителя по карточке",
)
def mark_card_event(id: str, payload: WinnerEventRequest) -> GameStateResponse:
    game = _get_game_or_404(id)
    if game["status"] == "finished":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "game_already_finished",
                "message": "Партия уже завершена",
                "details": {"id": id},
            },
        )
    if game["card_winner"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "card_winner_already_set",
                "message": "Победитель по карточке уже зафиксирован",
                "details": {"winner": game['card_winner']},
            },
        )
    _ensure_player(game, payload.player_id)
    game["card_winner"] = payload.player_id
    return GameStateResponse(
        id=id,
        status=game["status"],
        line_winner=game["line_winner"],
        card_winner=game["card_winner"],
    )


@router.post(
    "/{id}/finish",
    response_model=GameStateResponse,
    summary="Завершить партию",
)
def finish_game(id: str) -> GameStateResponse:
    game = _get_game_or_404(id)
    if game["status"] == "finished":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "game_already_finished",
                "message": "Партия уже завершена",
                "details": {"id": id},
            },
        )
    game["status"] = "finished"
    return GameStateResponse(
        id=id,
        status=game["status"],
        line_winner=game["line_winner"],
        card_winner=game["card_winner"],
    )


@router.get(
    "/{id}/settlement",
    response_model=SettlementResponse,
    summary="Получить расчет выплат по партии",
)
def get_settlement(id: str) -> SettlementResponse:
    game = _get_game_or_404(id)
    if game["status"] != "finished":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "game_not_finished",
                "message": "Сначала завершите партию",
                "details": {"id": id, "status": game["status"]},
            },
        )

    card_pot = game["card_price"] * len(game["players"])
    payouts = {player: 0.0 for player in game["players"]}

    card_prize = card_pot
    if game["line_winner"]:
        payouts[game["line_winner"]] += game["line_bonus"]
        card_prize -= game["line_bonus"]

    if game["card_winner"]:
        payouts[game["card_winner"]] += max(card_prize, 0.0)

    return SettlementResponse(
        id=id,
        status=game["status"],
        card_pot=card_pot,
        line_bonus=game["line_bonus"],
        payouts=payouts,
    )
