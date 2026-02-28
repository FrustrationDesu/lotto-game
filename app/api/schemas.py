from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Any | None = None


class CreateGameRequest(BaseModel):
    players: list[str] = Field(
        ...,
        description="Список уникальных идентификаторов игроков",
        examples=[["alice", "bob", "charlie"]],
    )
    card_price: float = Field(
        ...,
        gt=0,
        description="Цена карты в рублях",
        examples=[10],
    )
    line_bonus: float = Field(
        ...,
        gt=0,
        description="Бонус за линию в рублях",
        examples=[5],
    )

    @model_validator(mode="after")
    def validate_players(self) -> "CreateGameRequest":
        if len(self.players) < 2:
            raise ValueError("В партии должно быть минимум 2 игрока")
        if len(set(self.players)) != len(self.players):
            raise ValueError("Игроки в партии должны быть уникальными")
        return self

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "players": ["alice", "bob", "charlie"],
                    "card_price": 10,
                    "line_bonus": 5,
                }
            ]
        }
    }


class CreateGameResponse(BaseModel):
    id: str
    players: list[str]
    card_price: float
    line_bonus: float
    status: str


class WinnerEventRequest(BaseModel):
    player_id: str = Field(..., examples=["alice"])


class GameStateResponse(BaseModel):
    id: str
    status: str
    line_winner: str | None = None
    card_winner: str | None = None


class SettlementResponse(BaseModel):
    id: str
    status: str
    card_pot: float
    line_bonus: float
    payouts: dict[str, float]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "3ed7c88a-c4d5-453a-a437-1ad033f89a4a",
                    "status": "finished",
                    "card_pot": 30,
                    "line_bonus": 5,
                    "payouts": {"alice": 5, "bob": 25, "charlie": 0},
                }
            ]
        }
    }
