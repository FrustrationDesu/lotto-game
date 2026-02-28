from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.storage.database import Base, get_db
from app.storage.models import Game, GamePlayer
from app.services.stats_service import record_finished_game


def make_test_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
    return TestingSessionLocal()


def test_only_finished_games_in_aggregates() -> None:
    db = make_test_db()

    finished = Game(status="finished", finished_at=datetime(2024, 1, 2, 10, 0, 0))
    active = Game(status="active")
    db.add_all([finished, active])
    db.flush()

    db.add_all(
        [
            GamePlayer(game_id=finished.id, player_name="alice", buy_in=100, payout=150, card_closed=True),
            GamePlayer(game_id=finished.id, player_name="bob", buy_in=100, payout=50, card_closed=False),
            GamePlayer(game_id=active.id, player_name="alice", buy_in=100, payout=500, card_closed=True),
        ]
    )
    db.commit()

    record_finished_game(finished.id, db)

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    balance = client.get("/stats/balance")
    assert balance.status_code == 200
    data = balance.json()
    assert data["games_count"] == 1
    assert data["total_balance"] == 0.0
    players = {p["name"]: p["net"] for p in data["players"]}
    assert players == {"alice": 50.0, "bob": -50.0}

    player = client.get("/stats/player/alice")
    assert player.status_code == 200
    p_data = player.json()
    assert p_data["games_count"] == 1
    assert p_data["total_net"] == 50.0
    assert p_data["win_rate"] == 1.0
    assert len(p_data["history"]) == 1

    app.dependency_overrides.clear()
