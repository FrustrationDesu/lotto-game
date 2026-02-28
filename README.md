# Lotto Game Backend

Простой backend на **Python 3.11 + FastAPI** для учета денежных расчетов в лото.

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

## Правила расчета

1. В начале каждый игрок кладет в банк `card_price_kopecks`.
2. За каждое событие `line_closed` победителю(ям) платят все остальные по `line_bonus_kopecks`.
3. Банк делится между победителями(ем) карты (`card_closed`).
4. Все суммы хранятся в копейках (`int`) для точности.

## Быстрый старт

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
uvicorn app.main:app --reload
```

API будет доступно на `http://127.0.0.1:8000`, Swagger — `/docs`.

## Основные endpoints

- `POST /games` — создать игру
- `POST /games/{id}/events/line` — добавить закрытие линии
- `POST /games/{id}/events/card` — добавить закрытие карты
- `POST /games/{id}/finish` — завершить игру и зафиксировать результат
- `GET /games/{id}/settlement` — получить расчет завершенной игры
- `GET /stats/balance` — общий баланс по всем завершенным играм
- `POST /speech/transcribe` — распознавание речи из аудиофайла (`multipart/form-data`, поле `file`)

## Пример сценария

1. Создать игру на 4 игроков, карта = 1000 коп, линия = 500 коп.
2. Событие линии: `Альберт`, `Паша`.
3. Событие карты: `Паша`.
4. Завершить игру.
5. Посмотреть `GET /stats/balance` для накопительного итога между партиями.

## Тесты

```bash
pytest
```


## Speech-to-Text

Новый endpoint: `POST /speech/transcribe`.

Поддерживаемые MIME-типы:
- `audio/webm`
- `audio/wav`
- `audio/mpeg`

Ограничение размера файла задается переменной `MAX_AUDIO_FILE_SIZE_BYTES` (по умолчанию 10 MB).

Обязательные переменные окружения:
- `TRANSCRIPTION_PROVIDER=openai`
- `OPENAI_API_KEY=<your_api_key>`

Опциональные переменные:
- `OPENAI_BASE_URL` (по умолчанию `https://api.openai.com/v1`)
- `OPENAI_WHISPER_MODEL` (по умолчанию `whisper-1`)

Пример `curl`:

```bash
curl -X POST "http://127.0.0.1:8000/speech/transcribe" \
  -H "accept: application/json" \
  -F "file=@./sample.webm;type=audio/webm"
```

Пример ответа:

```json
{
  "text": "Привет, это тест",
  "language": "ru",
  "duration_seconds": 3.42,
  "provider": "openai"
}
```
