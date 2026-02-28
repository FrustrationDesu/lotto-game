# Lotto Game Backend

Простой backend на **Python 3.11 + FastAPI** для учета денежных расчетов в лото.

## Архитектура API

Целевая архитектура — **модульные роутеры** (`app/api/*`) с подключением в `app/main.py` через `app.include_router(...)`:

- `app/api/games.py` — игровой lifecycle и settlement.
- `app/api/stats.py` — агрегаты по завершенным играм.
- `app/api/speech.py` — voice-команды (`interpret`) и транскрибация (`transcribe`).

## Что уже реализовано

- Создание партии с параметрами:
  - цена карточки (`card_price_kopecks`)
  - доплата за линию (`line_bonus_kopecks`)
- События партии:
  - закрытие линии (может быть несколько победителей за событие)
  - закрытие карты (может быть несколько победителей)
- Ограничение: один и тот же игрок может закрыть линию только один раз за партию.
- Завершение партии с расчетом:
  - чистого баланса (`net`) по каждому игроку
  - списка переводов «кто кому должен» (`transfers`)
- Межпартийная статистика:
  - общий накопительный баланс по игрокам
  - количество завершенных партий
- Легкий фронт для сессий игр:
  - создание сессии
  - шаг «Кто закрыл линию?»
  - шаг «Кто закрыл карту?»
  - история игр в рамках одной сессии

## Правила расчета

1. В начале каждый игрок кладет в банк `card_price_kopecks`.
2. За каждое событие `line_closed` победителю(ям) платят все остальные по `line_bonus_kopecks`.
3. Банк делится между победителями(ем) карты (`card_closed`).
4. Все суммы хранятся в копейках (`int`) для точности.

## Быстрый старт

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API будет доступно на `http://127.0.0.1:8000`, Swagger — `/docs`, UI сессии — `/`.

## Финальный набор endpoints

### Games

- `POST /games`
- `POST /games/{game_id}/events/line`
- `POST /games/{game_id}/events/card`
- `POST /games/{game_id}/finish`
- `GET /games/{game_id}/settlement`

### Stats

- `GET /stats/balance`
- `GET /stats/player/{name}`

### Speech

- `POST /speech/interpret`
- `POST /speech/transcribe`

### Sessions (UI support)

- `POST /sessions`
- `POST /sessions/{session_id}/line`
- `POST /sessions/{session_id}/card`
- `POST /sessions/{session_id}/finish`
- `POST /sessions/{session_id}/new-game`
- `GET /sessions/{session_id}`

## Ошибки API

Для `games`, `stats`, `speech` используется единый формат ошибок:

```json
{
  "detail": {
    "code": "error_code",
    "message": "Human readable message",
    "details": {}
  }
}
```

## Тесты

```bash
pytest
```
