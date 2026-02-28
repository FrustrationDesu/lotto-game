# Lotto Game Backend

Простой backend на **Python 3.11 + FastAPI** для учета денежных расчетов в лото.

## Что реализовано

- Игровой API:
  - создание партии с параметрами (`card_price_kopecks`, `line_bonus_kopecks`)
  - фиксация событий по линии и карте (поддерживаются несколько победителей)
  - ограничение: один и тот же игрок может закрыть линию только один раз за партию
  - завершение партии с расчетом `net` и переводов `transfers`
  - межпартийная статистика по завершенным играм
- Session API:
  - создание сессии
  - пошаговое заполнение победителей (line/card)
  - завершение игры в сессии
  - история игр и старт новой игры в рамках одной сессии
- Встроенный UI для сессий (inline HTML в `app/main.py`, маршрут `/`).
- Отдельный `frontend/` — **демо-клиент** для записи/отправки аудио в speech-эндпоинт (не является основным игровым UI).

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

API будет доступно на `http://127.0.0.1:8000`, Swagger — `/docs`, основной UI сессии — `/`.

## Endpoints

### Таблица соответствия endpoint → статус реализации

| Endpoint | Метод | Статус | Примечание |
|---|---|---|---|
| `/` | GET | ✅ Реализован | Основной inline UI сессий из `app/main.py` |
| `/games` | POST | ✅ Реализован | Создание игры |
| `/games/{game_id}/events/line` | POST | ✅ Реализован | Добавление победителей линии |
| `/games/{game_id}/events/card` | POST | ✅ Реализован | Добавление победителей карты |
| `/games/{game_id}/finish` | POST | ✅ Реализован | Завершение игры и расчет |
| `/games/{game_id}/settlement` | GET | ✅ Реализован | Получение расчета завершенной игры |
| `/stats/balance` | GET | ✅ Реализован | Общий баланс по завершенным играм |
| `/sessions` | POST | ✅ Реализован | Создание сессии |
| `/sessions/{session_id}/line` | POST | ✅ Реализован | Установка победителей линии в активной игре |
| `/sessions/{session_id}/card` | POST | ✅ Реализован | Установка победителей карты в активной игре |
| `/sessions/{session_id}/finish` | POST | ✅ Реализован | Завершение активной игры сессии |
| `/sessions/{session_id}/new-game` | POST | ✅ Реализован | Новая игра в текущей сессии |
| `/sessions/{session_id}` | GET | ✅ Реализован | Состояние сессии и история |
| `/speech/transcribe` | POST | ❌ Не реализован в `app/main.py` | Endpoint упоминается в тестах/документации, но не объявлен в текущем FastAPI-приложении |
| `/speech/interpret` | POST | ❌ Не реализован в `app/main.py` | Endpoint упоминается в тестах, но не объявлен в текущем FastAPI-приложении |

## Frontend

Основным frontend в текущем приложении является **inline UI в `app/main.py`** (маршрут `/`).

Папка `frontend/` содержит отдельное демо-приложение для сценариев speech (запись через `MediaRecorder` и отправка аудио), но не является основным интерфейсом для игрового потока сессий.

## Speech provider env vars

Для OpenAI-провайдера транскрибации используются переменные окружения:

- `TRANSCRIPTION_PROVIDER` — провайдер транскрибации (текущее поддерживаемое значение: `openai`).
- `OPENAI_API_KEY` — API-ключ.
- `OPENAI_BASE_URL` — базовый URL API (по умолчанию `https://api.openai.com/v1`).
- `OPENAI_WHISPER_MODEL` — модель транскрибации (по умолчанию `whisper-1`).

Пример:

```bash
export TRANSCRIPTION_PROVIDER=openai
export OPENAI_API_KEY=your_key
export OPENAI_BASE_URL=https://api.openai.com/v1
export OPENAI_WHISPER_MODEL=whisper-1
```

## Тесты

```bash
pytest
```

Примечание: часть тестов в репозитории ожидает наличие speech-endpoints (`/speech/transcribe`, `/speech/interpret`), которые в текущем `app/main.py` не зарегистрированы.
