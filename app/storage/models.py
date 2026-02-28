from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.database import Base


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    card_price_kopecks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    line_bonus_kopecks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    players: Mapped[list["GamePlayer"]] = relationship(back_populates="game", cascade="all, delete-orphan")
    events: Mapped[list["GameEvent"]] = relationship(back_populates="game", cascade="all, delete-orphan")
    results: Mapped[list["GameResult"]] = relationship(back_populates="game", cascade="all, delete-orphan")


class GamePlayer(Base):
    __tablename__ = "game_players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False, index=True)
    player_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    buy_in: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    payout: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    card_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    game: Mapped[Game] = relationship(back_populates="players")


class GameEvent(Base):
    __tablename__ = "game_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False, index=True)
    player_name: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    game: Mapped[Game] = relationship(back_populates="events")


class GameResult(Base):
    __tablename__ = "game_results"
    __table_args__ = (UniqueConstraint("game_id", "player_name", name="uq_game_results_game_player"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False, index=True)
    player_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    net: Mapped[float] = mapped_column(Float, nullable=False)
    card_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    game: Mapped[Game] = relationship(back_populates="results")
