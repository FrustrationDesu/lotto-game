import importlib
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest



def _import_any(*candidates: str):
    for name in candidates:
        try:
            return importlib.import_module(name)
        except ModuleNotFoundError:
            continue
    pytest.fail(f"Не удалось импортировать ни один модуль из: {candidates}")


stats_module = _import_any("lotto_game.services.stats_service", "services.stats_service", "app.services.stats_service")

StatsService = getattr(stats_module, "StatsService", None)
if StatsService is None:
    pytest.fail("В модуле stats_service не найден класс StatsService")


@dataclass
class _Game:
    id: str
    status: str
    created_at: datetime


@pytest.mark.parametrize("games_count", [1, 5, 10])
def test_stats_aggregate_after_n_games(games_count: int):
    service = StatsService()

    games = [
        _Game(
            id=f"g-{idx}",
            status="finished",
            created_at=datetime.now(timezone.utc),
        )
        for idx in range(games_count)
    ]

    stats = service.aggregate(games)

    total_games = getattr(stats, "total_games", stats.get("total_games"))
    finished_games = getattr(stats, "finished_games", stats.get("finished_games"))

    assert total_games == games_count
    assert finished_games == games_count


def test_stats_ignores_unfinished_games():
    service = StatsService()

    games = [
        _Game(id="g-1", status="finished", created_at=datetime.now(timezone.utc)),
        _Game(id="g-2", status="in_progress", created_at=datetime.now(timezone.utc)),
        _Game(id="g-3", status="created", created_at=datetime.now(timezone.utc)),
    ]

    stats = service.aggregate(games)

    total_games = getattr(stats, "total_games", stats.get("total_games"))
    finished_games = getattr(stats, "finished_games", stats.get("finished_games"))

    assert total_games == 3
    assert finished_games == 1
